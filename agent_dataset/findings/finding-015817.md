---
id: 15817
severity: "High"
---

# Token withdrawal fails until someone manually approves spending

## Description

The protocol uses a contract called TokenManager to control a capital pool that stores tokens.

When a user wants to withdraw, the TokenManager needs spender allowance on the capital pool, but this is not checked for, so the withdrawal fails.

We simulate a user creating an offer, closing it and then trying to withdraw. The withdrawal fails because of zero allowance for the TokenManager as a spender of the capital pool.
```solidity
function testtokenwithdrawal_fails() public {
    // Data for creating an offer, not relevant.
    uint256 points = 1000;
    uint256 amountToken = 1000000 * 1e18;
    uint256 collateralRate = 12000;
    uint256 eachTradeTax = 300;

    vm.startPrank(user);
    preMarktes.createOffer(
        CreateOfferParams(
            marketPlace,
            address(mockUSDCToken),
            points,
            amountToken,
            collateralRate,
            eachTradeTax,
            OfferType.Ask,
            OfferSettleType.Turbo
        )
    );

    // Close the offer.
    address offerAddr = GenerateAddress.generateOfferAddress(0);
    address stockAddr = GenerateAddress.generateStockAddress(0);

    preMarktes.closeOffer(stockAddr, offerAddr);

    tokenManager.withdraw(address(mockUSDCToken), TokenBalanceType.MakerRefund);
    vm.stopPrank();
}
```
```solidity
├─ [8858] UpgradeableProxy::withdraw(MockERC20Token: [0xF62849F9A0B5Bf2913b396098F7c7019b51A820a], 4)
│   ├─ [8339] TokenManager::withdraw(MockERC20Token: [0xF62849F9A0B5Bf2913b396098F7c7019b51A820a], 4) [delegatecall]
│   │   ├─ [534] TadleFactory::relatedContracts(4) [staticcall]
│   │   │   └─ ← [Return] UpgradeableProxy: [0x76006C4471fb6aDd17728e9c9c8B67d5AF06cDA0]
│   │   ├─ [2959] MockERC20Token::transferFrom(UpgradeableProxy: [0x76006C4471fb6aDd17728e9c9c8B67d5AF06cDA0], 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf, 1200000000000000000000000 [1.2e24])
│   │   │   └─ ← [Revert] ERC20InsufficientAllowance(0x6891e60906DEBeA401F670D74d01D117a3bEAD39, 0, 1200000000000000000000000 [1.2e24])
│   │   └─ ← [Revert] TransferFailed()
│   └─ ← [Revert] TransferFailed()
└─ ← [Revert] TransferFailed()
```
For every new token whitelisted into the protocol, users will be unable to withdraw them until somebody calls `capitalPool.approve(address(token))`. Because there's a disruption of protocol functionality, I am reporting this as MEDIUM.

When someone calls the approve, TokenManager gets an allowance of uint.MAX on one of the capital pool's tokens, which means it withdrawals should work for the foreseeable future.

## Proof of Concept

no poc

## Recommendation

In TokenManager::withdraw, line 175, before the safe transfer from call, check and add allowance if necessary:
```solidity
if (IERC20(_tokenAddress).allowance(capitalPoolAddr, address(this)) == 0x0) {
    ICapitalPool(capitalPoolAddr).approve(_tokenAddress);
}
```
By doing that, the withdrawal no longer fails:
```solidity
[PASS] testtokenwithdrawal_fails() (gas: 612289)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing allowance check in the TokenManager.withdraw function that prevents the contract from moving tokens out of the protocol’s capital pool. When a user closes an offer and calls withdraw, TokenManager attempts to call transferFrom on the ERC20 token using the capital pool as the source. Because the capital pool has never granted an allowance to TokenManager for that token, the ERC20 contract reverts with an ERC20InsufficientAllowance error. This situation occurs for any token that is newly whitelisted in the protocol; the capital pool’s allowance for TokenManager defaults to zero until an external actor manually calls capitalPool.approve(tokenAddress). From the user’s perspective the withdrawal transaction fails, the UI may show that the balance after the operation is unchanged or even zero, and the expected refund never arrives. The impact is that users are unable to retrieve their deposited tokens, effectively locking funds and disrupting normal protocol operation. The issue was discovered during an audit when a test scenario simulated creating an offer, closing it, and then withdrawing; the transaction reverted due to insufficient allowance. The bug is subtle because it only manifests for tokens that have not been pre‑approved, so it can be missed if tests only cover already‑approved assets. Conceptually, this is a classic “missing approval” or “allowance dependency” bug where a contract assumes an external allowance exists without ensuring it. The proper fix is to have TokenManager verify the allowance before calling transferFrom and, if it is zero, invoke an approve on the capital pool to grant itself a sufficient (typically uint.MAX) allowance, or redesign the flow to use safeTransfer instead of transferFrom. By adding this check, withdrawals succeed and user funds are no longer stuck.

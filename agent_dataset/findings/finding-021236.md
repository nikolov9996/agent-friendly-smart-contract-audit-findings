---
id: 21236
severity: "High"
---

# Incorrect calculation of queued withdrawals can deflate TVL and increase ezETH mint rate

## Description

The function [`OperatorDelegator.getTokenBalanceFromStrategy()`](https://github.com/code-423n4/2024-04-renzo/blob/519e518f2d8dec9acf6482b84a181e403070d22d/contracts/Delegation/OperatorDelegator.sol#L327) is used by the [`RestakeManager`](https://github.com/code-423n4/2024-04-renzo/blob/519e518f2d8dec9acf6482b84a181e403070d22d/contracts/RestakeManager.sol) to calculate the protocol TVL, which in turn is used to calculate the amount of ezETH to mint against a given value in collateral tokens.

This function, however, incorrectly checks for the queued amount of `address(this)` instead of `address(token)`; therefore, consistently failing to consider collaterals in the withdrawal process for calculation:

```solidity
/// @dev Gets the underlying token amount from the amount of shares + queued withdrawal shares
function getTokenBalanceFromStrategy(IERC20 token) external view returns (uint256) {
    return
        queuedShares[address(this)] == 0
            ? tokenStrategyMapping[token].userUnderlyingView(address(this))
            : tokenStrategyMapping[token].userUnderlyingView(address(this)) +
                tokenStrategyMapping[token].sharesToUnderlyingView(
                    queuedShares[address(token)]
                );
}
```

Within this code, `queuedShares[address(this)]` will always return `0`; therefore, missing the opportunity to count the contribution of `queuedShares[address(token)]`.

## Proof of Concept

The following PoC in Foundry shows how the issue can lead to a decrease in TVL. The PoC can be run in Foundry by using the setup and mock infra provided [here](https://gist.github.com/3docSec/a4bc6254f709a6218907a3de370ae84e).

```solidity
pragma solidity ^0.8.19;

import "contracts/Errors/Errors.sol";
import "./Setup.sol";

contract H2 is Setup {

    function testH2() public {
        // we'll only be using stETH with unitary price for simplicity
        stEthPriceOracle.setAnswer(1e18);

        // and we start with 0 TVL
        (, , uint tvl) = restakeManager.calculateTVLs();
        assertEq(0, tvl);

        // now we have Alice depositing some stETH
        address alice = address(1234567890);
        stETH.mint(alice, 100e18);
        vm.startPrank(alice);
        stETH.approve(address(restakeManager), 100e18);
        restakeManager.deposit(IERC20(address(stETH)), 100e18);

        // ✅ TVL and balance are as expected
        (, , tvl) = restakeManager.calculateTVLs();
        assertEq(100e18, tvl);
        assertEq(100e18, ezETH.balanceOf(alice));

        // Now some liquidity enters the withdraw sequence
        vm.startPrank(OWNER);

        IERC20[] memory tokens = new IERC20[](1);
        uint256[] memory tokenAmounts = new uint256[](1);

        tokens[0] = IERC20(address(stETH));
        tokenAmounts[0] = 50e18;

        operatorDelegator1.queueWithdrawals(tokens, tokenAmounts);

        // 🚨 The collateral queued for withdrawal does not show up in TVL,
        // so the mint rate is altered
        (, , tvl) = restakeManager.calculateTVLs();
        assertEq(50e18, tvl);
    }
}
```

## Recommendation

Consider changing the address used for the mapping lookup:

```solidity
/// @dev Gets the underlying token amount from the amount of shares + queued withdrawal shares
function getTokenBalanceFromStrategy(IERC20 token) external view returns (uint256) {
    return
        queuedShares[address(token)] == 0
            ? tokenStrategyMapping[token].userUnderlyingView(address(this))
            : tokenStrategyMapping[token].userUnderlyingView(address(this)) +
                tokenStrategyMapping[token].sharesToUnderlyingView(
                    queuedShares[address(token)]
                );
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect accounting routine used to compute the protocol’s total value locked (TVL) and the amount of ezETH that can be minted against deposited collateral. The function that aggregates a token’s underlying balance adds the value of shares held by the strategy and, when applicable, the value of shares that have been queued for withdrawal. However, the condition that decides whether queued shares should be added checks the mapping entry for the contract’s own address (address(this)) instead of the specific token address. Because the contract never records queued shares under its own address, the check always evaluates to zero, causing the function to ignore any pending withdrawals for that token. As a result, when a user or the operator queues a withdrawal, the amount that is slated to leave the system is omitted from the TVL calculation. The protocol therefore reports a lower TVL than the actual assets under management. Since the ezETH minting formula uses the reported TVL as a denominator, a deflated TVL inflates the mint rate, allowing more ezETH to be minted per unit of collateral than intended. An attacker can trigger withdrawals for a chosen token, watch the TVL drop, and then deposit additional collateral to receive an oversized amount of ezETH, effectively diluting existing holders and stealing value from the protocol. The impact is economic: users may receive more ezETH than they should, the protocol’s accounting becomes inconsistent, and the perceived health of the system is misrepresented, potentially leading to loss of confidence and financial loss for honest participants. The bug manifests whenever the RestakeManager calls getTokenBalanceFromStrategy while there are queued withdrawals for any supported collateral token. It is difficult to notice because the TVL simply appears lower; the UI may show a reduced total locked amount without obvious error, and the minting process still succeeds, masking the underlying mis‑calculation. The issue was discovered during a formal audit, where a Foundry proof‑of‑concept demonstrated that after queuing a withdrawal of 50 stETH the reported TVL fell from 100 stETH to 50 stETH, confirming that the queued amount was ignored. To remediate, the accounting function must reference the queuedShares entry for the token address (queuedShares[address(token)]) when deciding whether to add the pending withdrawal value, ensuring that all assets slated to leave the protocol are correctly reflected in the TVL and that the ezETH mint rate remains accurate.

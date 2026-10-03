---
id: 25700
severity: "Crit/High"
---

# Liquidations miss delegate call to swapper

## Description



## Proof of Concept

## Vulnerability Detail

The LiquidationRow contract is an orchestrator for the claiming process. It is primarily used to collect rewards for vaults. It has a method called **liquidateVaultsForToken**. Based on docs this method is for: *Conducts the liquidation process for a specific token across a list of vaults, performing the necessary balance adjustments, initiating the swap process via the asyncSwapper, taking a fee from the received amount, and queues the remaining swapped tokens in the MainRewarder associated with each vault.*

```solidity
function liquidateVaultsForToken(
    address fromToken,
    address asyncSwapper,
    IDestinationVault[] memory vaultsToLiquidate,
    SwapParams memory params
) external nonReentrant hasRole(Roles.LIQUIDATOR_ROLE) onlyWhitelistedSwapper(asyncSwapper) {
    uint256 gasBefore = gasleft();

    (uint256 totalBalanceToLiquidate, uint256[] memory vaultsBalances) =
        _prepareForLiquidation(fromToken, vaultsToLiquidate);
    _performLiquidation(
        gasBefore, fromToken, asyncSwapper, vaultsToLiquidate, params, totalBalanceToLiquidate, vaultsBalances
    );
}
```

> [https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L167C5-L180C6](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L167C5-L180C6>)

The second part of the function is performing the liquidation by calling **_performLiquidation**. A problem is at the beginning of it. IAsyncSwapper is called to swap tokens.

```solidity
function _performLiquidation(
    uint256 gasBefore,
    address fromToken,
    address asyncSwapper,
    IDestinationVault[] memory vaultsToLiquidate,
    SwapParams memory params,
    uint256 totalBalanceToLiquidate,
    uint256[] memory vaultsBalances
) private {
    uint256 length = vaultsToLiquidate.length;
    // the swapper checks that the amount received is greater or equal than the params.buyAmount
    uint256 amountReceived = IAsyncSwapper(asyncSwapper).swap(params);
    // ...
}
```

> [https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L251C8-L251C75](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L251C8-L251C75>)

As you can see the LiquidationRow doesn't transfer the tokens to swapper and swapper doesn't pul them either ([swap function here](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/BaseAsyncSwapper.sol#L19C5-L64C6>)). Because of this the function reverses.

I noticed that there is no transfer back to LiquidationRow from Swapper either. Tokens can't get in or out.

When I searched the codebase, I found that Swapper is being called on another place using the delegatecall method. This way it can operate with the tokens of the caller. The call can be found here - [LMPVaultRouter.sol:swapAndDepositToVault](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVaultRouter.sol#L53C8-L55C11>). So I think that instead of missing transfer, the problem is actually in the way how swapper is called.

## Impact

Rewards collected through LiquidationRow **claimsVaultRewards** get stuck in the contract. Liquidation can't be called because it reverts when Swapper tries to work with tokens it doesn't possess.

## Code Snippet

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L167C5-L180C6](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L167C5-L180C6>)

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L251C8-L251C75](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/LiquidationRow.sol#L251C8-L251C75>)

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/BaseAsyncSwapper.sol#L19C5-L64C6](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/liquidation/BaseAsyncSwapper.sol#L19C5-L64C6>)

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVaultRouter.sol#L53C8-L55C11](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVaultRouter.sol#L53C8-L55C11>)

## Recommendation

Change the async swapper call from the normal function call to the low-level delegatecall function the same way it is done in LMPVaultRouter.sol:swapAndDepositToVault.

I would like to address that AsyncSwapperMock in LiquidationRow.t.sol is a poorly written mock and should be updated to represent how the AsyncSwapper work. It would be nice to update the test suite for LiquidationRow because its current state won't catch this. If you check the LiquidationRow.t.sol tests, the mock swap function only mints tokens, no need to use delegatecall. This is why tests missed this vulnerability.

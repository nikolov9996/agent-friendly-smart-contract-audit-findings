---
id: 25115
severity: "Crit/High"
---

# Lack of slippage protection leads to loss of protocol funds

## Description



## Proof of Concept

## Vulnerability Detail

There are 2 intances where slippage protection is missing which are as below:

1. When LV token holder redeem before expiry `vaultLib::redeemEarly` function is called in which `_liquidateLpPartial` function and in that `_redeemCtDsAndSellExcessCt` is called. In `_redeemCtDsAndSellExcessCt` function CT tokens are swapped for RA tokens in AMM as below:

```solidity
...
ra += ammRouter.swapExactTokensForTokens(ctSellAmount, 0, path, address(this), block.timestamp)[1];
...
```

As stated above, `swapExactTokensForTokens` function's 2nd parameter is 0 which shows that there is no slippage protection for this swap and also deadline is block.timestamp.

2. In `vaultLib::_liquidateLpPartial` function `__liquidateUnchecked` is called in which liquidity is removed from AMM of RA-CT token pair by burning LP tokens of protocol as below:

```solidity
...
(raReceived, ctReceived) =
            ammRouter.removeLiquidity(raAddress, ctAddress, lp, 0, 0, address(this), block.timestamp);
...
```

As stated above, `removeLiquidity` function's 4th & 5th parameter is 0 which shows that there is no slippage protection for this swap and also deadline is block.timestamp.

In such cases, an attacker can frontrun the transaction by seeing it in the mempool and manipulate the price such that protocol transaction have to bear heavy slippage which will leads to loss of protocol funds.

Also, there is block.timestamp as deadline so malicious node can prevent transaction to execute temporary and execute the transaction when there is high slippage which will also leads to loss of protocol funds.

## Impact

Loss of protocol funds which will reduce the yield of users.

## Code Snippet

[https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L282](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L282>)

[https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L345](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L345>)

## Recommendation

Protocol should implement slippage protection and set deadline while removing liquidity and also swap from AMM.

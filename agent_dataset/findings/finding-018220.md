---
id: 18220
severity: "High"
---

# Price of sfrxEth derivative is calculated incorrectly

## Description

In the [ethPerDerivative()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L111-L117), the calculated `frxAmount` is multiplied by (10 ** 18) and divided by `price_oracle`, but it must be multiplied by `price_oracle` and divided by (10 ** 18).

The impact is severe as [ethPerDerivative()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L111-L117) function is used in [stake()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/SafEth.sol#L63-L101), one of two main functions a user will interact with. The value returned by [ethPerDerivative()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L111-L117) affects the calculations of [`mintAmount`](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/SafEth.sol#L98). The incorrect calculation may over or understate the amount of safEth received by the user.

[ethPerDerivative()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L111-L117) is also used in the [withdraw()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L60-L88) function when calculating [`minOut`](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L74). So, incorrect calculation of ethPerDerivative() may increase/decrease slippage. This can cause unexpected losses or function revert. If [withdraw()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L60-L88) function reverts, the function [unstake()](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/SafEth.sol#L108-L129) is unavailable => assets are locked.

## Proof of Concept

We need to calculate: (10 ** 18) sfrxEth = X Eth.

For example, we `convertToAssets(10 ** 18)` and get `frxAmount` = 1031226769652703996. `price_oracle` returns 998827832404234820. So, (10 ** 18) frxEth costs 998827832404234820 Eth. Thus, (10 ** 18) sfrxEth costs `frxAmount * price_oracle / 10 ** 18` = 1031226769652703996 * 998827832404234820 / 10 ** 18 Eth (1030017999049431492 Eth).

But [this function](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L111-L117):

```solidity
function ethPerDerivative(uint256 _amount) public view returns (uint256) {
    uint256 frxAmount = IsFrxEth(SFRX_ETH_ADDRESS).convertToAssets(10 ** 18);
    return ((10 ** 18 * frxAmount) / IFrxEthEthPool(FRX_ETH_CRV_POOL_ADDRESS).price_oracle());
}
```

calculates the cost of sfrxEth as `10 ** 18 * frxAmount / price_oracle` = 10 ** 18 * 1031226769652703996 / 998827832404234820 Eth (1032436958800480269 Eth). The current difference ~ 0.23% but it can be more/less.

## Recommendation

Change [these lines](https://github.com/code-423n4/2023-03-asymmetry/blob/main/contracts/SafEth/derivatives/SfrxEth.sol#L115-L116):

```solidity
return ((10 ** 18 * frxAmount) / IFrxEthEthPool(FRX_ETH_CRV_POOL_ADDRESS).price_oracle());
```

to:

```solidity
return (frxAmount * IFrxEthEthPool(FRX_ETH_CRV_POOL_ADDRESS).price_oracle() / 10 ** 18);
```

To protect against oracle attacks we assume FRX is 1:1 with ETH and revert if the oracle says otherwise since there is no chainlink for FRX.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic mis‑ordering in the function that converts a wrapped FRX‑ETH derivative (sfrxEth) to its underlying ETH value. Instead of multiplying the amount of wrapped tokens by the price oracle and then dividing by the fixed‑point scaling factor (10**18), the code multiplies by the scaling factor first and divides by the oracle value. This reversal of the multiplication/division order produces a systematic rounding error that can over‑ or under‑state the ETH value of a derivative by a few basis points, and potentially more under extreme price conditions. The root cause is a simple formula mistake: the contract uses ((10**18 * frxAmount) / price_oracle) where the correct expression should be (frxAmount * price_oracle / 10**18). Because the function ethPerDerivative() is called by the public stake() entry point to compute how many safEth tokens a user should receive for a given deposit, an incorrect price leads to users receiving either too many or too few safEth tokens than the protocol’s accounting expects. The same mis‑calculation is also used in withdraw() to compute the minimum output amount (minOut), so the error propagates to slippage calculations and can cause the withdraw transaction to revert. When a withdraw reverts, the companion unstake() function becomes unavailable, effectively locking the user’s assets in the contract. The issue is observable from a user’s perspective as a mismatch between the amount of ETH they deposit and the amount of safEth they receive, or as a failed withdrawal where the UI reports a transaction revert or a missing refund. The bug was discovered during a formal security audit (Code4rena) by reviewing the arithmetic in the derivative contract; it is subtle because the numerical discrepancy is small (around 0.2 % in the provided example) and may only surface under certain oracle price conditions, making it easy to miss in casual testing. The vulnerability belongs to the class of “incorrect financial formula” or “price conversion arithmetic error” bugs, which violate the protocol’s accounting invariants that assume a 1:1 relationship between FRX‑ETH and ETH when adjusted by the oracle. To remediate, the formula should be rewritten to multiply by the oracle price first and then divide by the scaling factor, and an additional sanity check should be added to revert if the oracle price deviates from the expected 1:1 ratio, thereby protecting against oracle manipulation. Properly fixing the calculation restores correct minting amounts, accurate slippage estimates, and ensures that withdrawals and unstaking remain functional, preserving user funds and protocol integrity.

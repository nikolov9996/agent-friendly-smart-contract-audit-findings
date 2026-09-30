---
id: 19268
severity: "High"
---

# `price`

## Description

In `AfEth.sol`, the `price()` function returns the current price of afEth:

[AfEth.sol#L133-L141](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L133-L141)
```solidity
function price() public view returns (uint256) {
    if (totalSupply() == 0) return 1e18;
    AbstractStrategy vEthStrategy = AbstractStrategy(vEthAddress);
    uint256 safEthValueInEth = (ISafEth(SAF_ETH_ADDRESS).approxPrice(true) *
        safEthBalanceMinusPending()) / 1e18;
    uint256 vEthValueInEth = (vEthStrategy.price() *
        vEthStrategy.balanceOf(address(this))) / 1e18;
    return ((vEthValueInEth + safEthValueInEth) * 1e18) / totalSupply();
}
```

As seen from above, the price of afEth is calculated by the TVL of both safEth and vAfEth divided by `totalSupply()`. However, this calculation does not take into account afEth that is transferred to the contract when `requestWithdraw()` is called:

[AfEth.sol#L183-L187](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L183-L187)
```solidity
uint256 afEthBalance = balanceOf(address(this));
uint256 withdrawRatio = (_amount * 1e18) /
    (totalSupply() - afEthBalance);

_transfer(msg.sender, address(this), _amount);
```

When a user calls `requestWithdraw()` to initiate a withdrawal, his afEth is transferred to the `AfEth` contract as shown above. Afterwards, an amount of [vAfEth proportional to his withdrawal amount is burned](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/strategies/votium/VotiumStrategy.sol#L54-L60), and [`pendingSafEthWithdraws` is increased](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L199).

When `price()` is called afterwards, `safEthBalanceMinusPending()` and `vEthStrategy.balanceOf(address(this))` will be decreased. However, since the user’s afEth is only transferred and not burnt, `totalSupply()` remains the same. This causes the value returned by `price()` to be lower than what it should be, since `totalSupply()` is larger than the actual circulating supply of afEth.

This is an issue as `deposit()` relies on `price()` to determine how much afEth to mint to a depositor:

[AfEth.sol#L166-L168](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L166-L168)
```solidity
uint256 amountToMint = totalValue / priceBeforeDeposit;
if (amountToMint < _minout) revert BelowMinOut();
_mint(msg.sender, amountToMint);
```

Where:

* `totalValue` is the ETH value of the caller’s deposit.
* `priceBeforeDeposit` is the cached value of `price()`.

If anyone has initiated a withdrawal using `requestWithdraw()` but hasn’t called `withdraw()` to withdraw his funds, `price()` will be lower than what it should be. Subsequently, when `deposit()` is called, the depositor will receive more afEth than he should since `priceBeforeDeposit` is smaller.

Furthermore, a first depositor can call `requestWithdraw()` with all his afEth immediately after staking to make `price()` return 0, thereby permanently DOSing all future deposits as `deposit()` will always revert with a division by zero error.

## Proof of Concept

Assume that the protocol is newly deployed and Alice is the only depositor.

* This means that Alice’s afEth balance equals to `totalSupply()`.

Alice calls `requestWithdraw()` with `_amount` as all her afEth:

* Since `_amount == totalSupply()`, `withdrawRatio` is `1e18` (100%).
* Therefore, all of the protocol’s vAfEth is burnt and `pendingSafEthWithdraws` is increased to the protocol’s safEth balance.
* Alice’s afEth is transferred to the protocol.

Bob calls `deposit()` to deposit some ETH into the protocol:

* When `price()` is called:

  * Since `pendingSafEthWithdraws` is equal to the protocol’s safEth balance, `safEthBalanceMinusPending()` is 0, therefore `safEthValueInEth` is also 0.
  * Since `vEthStrategy.balanceOf(address(this))` (the protocol’s vAfEth balance) is 0, `vEthValueInEth` is also 0.
  * `totalSupply()` is non-zero.
  * Therefore, `price()` returns 0 as:

      ((vEthValueInEth + safEthValueInEth) * 1e18) / totalSupply() = ((0 + 0) * 1e18) / x = 0

* As `priceBeforeDeposit` is 0, [this line](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L166) reverts with a division by zero error.

As demonstrated above, `deposit()` will always revert as long as Alice does not call `withdraw()` to burn her afEth, thereby bricking the protocol’s core functionality.

## Recommendation

In `price()`, consider subtracting the amount of afEth held in the contract from `totalSupply()`:

[AfEth.sol#L133-L141](https://github.com/code-423n4/2023-09-asymmetry/blob/main/contracts/AfEth.sol#L133-L141)
```solidity
function price() public view returns (uint256) {
    uint256 circulatingSupply = totalSupply() - balanceOf(address(this));
    if (circulatingSupply == 0) return 1e18;
    AbstractStrategy vEthStrategy = AbstractStrategy(vEthAddress);
    uint256 safEthValueInEth = (ISafEth(SAF_ETH_ADDRESS).approxPrice(true) *
        safEthBalanceMinusPending()) / 1e18;
    uint256 vEthValueInEth = (vEthStrategy.price() *
        vEthStrategy.balanceOf(address(this))) / 1e18;
    return ((vEthValueInEth + safEthValueInEth) * 1e18) / circulatingSupply;
}
```

I think we can solve this by burning the tokens in requestWithdraw.

For this one we made afEth just burn on requestWithdraw.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the protocol computes the market price of its wrapper token. The price function aggregates the value of two underlying strategies and divides that sum by the total token supply, but it fails to exclude the tokens that are temporarily held by the contract itself when a user initiates a withdrawal. When requestWithdraw transfers the caller's wrapper tokens to the contract, those tokens remain in the contract’s balance and are not burned, yet totalSupply stays unchanged. Consequently the denominator of the price formula is inflated relative to the actual circulating supply, causing the reported price to be artificially low. If a withdrawal is pending, the price can drop to zero because the underlying asset balances are reduced while totalSupply is still positive. This mis‑pricing is then used by the deposit function, which relies on the price value to determine how many wrapper tokens to mint for a new depositor. A lower price makes the contract think each unit of deposited ETH is worth more wrapper tokens, so the depositor receives an excessive amount of tokens. In the extreme case where a user withdraws the entire supply and leaves the tokens in the contract, the price calculation yields zero, triggering a division‑by‑zero revert in the deposit routine and effectively denying any further deposits. The issue is triggered whenever requestWithdraw is called without a subsequent withdraw, i.e., when pending withdrawals exist. It affects all participants who rely on accurate pricing – depositors receive too many tokens, the protocol’s accounting becomes inconsistent, and an attacker can permanently halt new deposits. The flaw was uncovered during a manual audit that examined the interaction between price, requestWithdraw, and deposit logic; the subtle mismatch between circulating supply and totalSupply made the bug easy to overlook because the price appears correct when no withdrawals are pending. The problem belongs to the class of accounting‑logic errors where a contract’s internal accounting does not correctly reflect token circulation, leading to price distortion and potential denial‑of‑service. To remediate, the price function should compute the circulating supply as totalSupply minus the contract’s own balance (or alternatively burn the tokens on requestWithdraw) before performing the division, thereby aligning the denominator with the actual amount of tokens that can be freely transferred. This adjustment restores correct price signals, prevents over‑minting on deposits, and eliminates the zero‑price edge case that can brick the protocol.

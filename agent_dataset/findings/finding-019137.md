---
id: 19137
severity: "High"
---

# The settle feature will be broken if attacker arbitrarily transfer collateral tokens to the PerpetualAtlanticVaultLP

## Description

`RdpxV2Core.settle` reverts and the protocol stops.

## Proof of Concept

If a collateral token(WETH) is arbitrarily sent to PerpetualAtlanticVaultLP, the values of `collateral.balanceOf(address(this))` and `_totalCollateral` will be different.

Since `PerpetualAtlanticVaultLP.subtractLoss` requires that `collateral.balanceOf(address(this))` exactly match with `_totalCollateral - loss`, `PerpetualAtlanticVaultLP.subtractLoss` will be failed if an attacker arbitrarily transfers collateral tokens to the PerpetualAtlanticVaultLP contract.

```solidity
function subtractLoss(uint256 loss) public onlyPerpVault {
  require(
    collateral.balanceOf(address(this)) == _totalCollateral - loss,
    "Not enough collateral was sent out"
  );
  _totalCollateral -= loss;
}
```

Since there is no function that synchronizes `_totalCollateral` with `collateral.balanceOf(address(this))` without moving tokens, even admin cannot fix.

This is exploit PoC. Add this test case at `tests/perp-vault/Unit.t.sol`

```solidity
function testSettlePoC() public {
  weth.mint(address(1), 1 ether);
  weth.mint(address(777), 1 ether); // give some tokens to attacker

  deposit(1 ether, address(1));

  vault.purchase(1 ether, address(this));

  uint256[] memory ids = new uint256[](1);
  ids[0] = 0;

  skip(86500); // expire

  priceOracle.updateRdpxPrice(0.010 gwei); // ITM
  uint256 wethBalanceBefore = weth.balanceOf(address(this));
  uint256 rdpxBalanceBefore = rdpx.balanceOf(address(this));

  // attack
  vm.startPrank(address(777), address(777));
  weth.transfer(address(vaultLp), 1); // send 1 wei of collateral
  vm.stopPrank();

  vm.expectRevert("Not enough collateral was sent out");
  vault.settle(ids);
}
```

## Recommendation

Use `>=` instead of `==` at `PerpetualAtlanticVaultLP.subtractLoss`

```solidity
function subtractLoss(uint256 loss) public onlyPerpVault {
  require(
    collateral.balanceOf(address(this)) >= _totalCollateral - loss,
    "Not enough collateral was sent out"
  );
  _totalCollateral -= loss;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting invariant violation in the PerpetualAtlanticVaultLP contract. The contract keeps an internal variable _totalCollateral that records the amount of collateral that should be held. When a loss is settled, the function subtractLoss checks that the ERC‑20 balance of the collateral token held by the contract exactly equals _totalCollateral minus the loss, using a strict equality (==) comparison. Because the check requires exact equality, any external transfer of collateral tokens into the vault changes the on‑chain balance without updating _totalCollateral. An attacker can arbitrarily send a small amount of the collateral token (e.g., 1 wei of WETH) to the vault LP contract. After the transfer, collateral.balanceOf(address(this)) becomes larger than the expected value, causing the require statement to revert with "Not enough collateral was sent out". The revert propagates to RdpxV2Core.settle, which then aborts the settlement process and halts the protocol. This can be triggered at any time after a position is ready to settle, simply by sending tokens to the vault address; no special permissions are required. The affected parties are all users who rely on the settle function to receive their payouts, as the protocol becomes unable to distribute funds, effectively locking user balances. The issue was discovered during a formal audit by Code4rena, where a test case demonstrated that an arbitrary token transfer caused settle to revert. The bug is hard to notice because the contract does not provide a function to reconcile the internal accounting with the actual token balance, so the mismatch remains hidden until a settlement is attempted. The proper fix is to relax the invariant check to allow the on‑chain balance to be greater than or equal to the expected amount (using >=) and to adjust _totalCollateral accordingly, or to implement a synchronization mechanism that updates the internal accounting when external token transfers occur. In user‑facing terms, a trader expects a settlement to credit their account, but instead receives no funds and sees the transaction fail with an error, leading to confusion and potential loss of confidence. The vulnerability belongs to the class of “invariant violation due to strict equality on external token balances”, which can cause funds to become inaccessible when external token transfers are possible.

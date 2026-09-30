---
id: 10549
severity: "High"
---

# `PortalFacet.repayAavePortal`

## Description

[PortalFacet.sol#L80-L113](https://github.com/code-423n4/2022-06-connext/blob/main/contracts/contracts/core/connext/facets/PortalFacet.sol#L80-L113)  

The caller of `repayAavePortal()` can trigger an underflow to arbitrarily increase the caller’s balance through an underflow.

## Proof of Concept

// Relevant code sections:

```solidity
// PortalFacet.sol
function repayAavePortal(
  address _local,
  uint256 _backingAmount,
  uint256 _feeAmount,
  uint256 _maxIn,
  bytes32 _transferId
) external {
  uint256 totalAmount = _backingAmount + _feeAmount; // in adopted
  uint256 routerBalance = s.routerBalances[msg.sender][_local]; // in local

  // Sanity check: has that much to spend
  if (routerBalance < _maxIn) revert PortalFacet__repayAavePortal_insufficientFunds();

  // Need to swap into adopted asset or asset that was backing the loan
  // The router will always be holding collateral in the local asset while the loaned asset
  // is the adopted asset

  // Swap for exact `totalRepayAmount` of adopted asset to repay aave
  (bool success, uint256 amountIn, address adopted) = AssetLogic.swapFromLocalAssetIfNeededForExactOut(
    _local,
    totalAmount,
    _maxIn
  );

  if (!success) revert PortalFacet__repayAavePortal_swapFailed();

  // decrement router balances
  unchecked {
    s.routerBalances[msg.sender][_local] -= amountIn;
  }

  // back loan
  _backLoan(_local, _backingAmount, _feeAmount, _transferId);
}

// AssetLogic.sol
function swapFromLocalAssetIfNeededForExactOut(
  address _asset,
  uint256 _amount,
  uint256 _maxIn
)
  internal
  returns (
    bool,
    uint256,
    address
  )
{
  AppStorage storage s = LibConnextStorage.connextStorage();

  // Get the token id
  (, bytes32 id) = s.tokenRegistry.getTokenId(_asset);

  // If the adopted asset is the local asset, no need to swap
  address adopted = s.canonicalToAdopted[id];
  if (adopted == _asset) {
    return (true, _amount, _asset);
  }

  return _swapAssetOut(id, _asset, adopted, _amount, _maxIn);
}
```

First, call `repayAavePortal()` where `_backingAmount + _feeAmount > s.routerBalances[msg.sender][_local] && _maxIn > s.routerBalances[msg.sender][_local]`. That will trigger the call to the AssetLogic contract:

```solidity
(bool success, uint256 amountIn, address adopted) = AssetLogic.swapFromLocalAssetIfNeededForExactOut(
  _local,
  totalAmount,
  _maxIn
);
```

By setting `_local` to the same value as the adopted asset, you trigger the following edge case:

```solidity
address adopted = s.canonicalToAdopted[id];
if (adopted == _asset) {
  return (true, _amount, _asset);
}
```

So the `amountIn` value returned by `swapFromLocalAssetIfNeededForExactOut()` is the `totalAmount` value that was passed to it. And `totalAmount == _backingAmount + _feeAmount`.

Meaning the `amountIn` value is user-specified for this edge case. Finally, we reach the following line:

```solidity
unchecked {
  s.routerBalances[msg.sender][_local] -= amountIn;
}
```

`amountIn` (user-specified) is subtracted from the `routerBalances` in an `unchecked` block. Thus, the attacker is able to trigger an underflow and increase their balance arbitrarily high. The `repayAavePortal()` function only verifies that `routerBalance < _maxIn`.

Here’s a test as PoC:

```solidity
// PortalFacet.t.sol
function test_PortalFacet_underflow() public {
  s.routerPermissionInfo.approvedForPortalRouters[router] = true;

  uint backing = 2 ether;
  uint fee = 10000;
  uint init = 1 ether;

  s.routerBalances[router][_local] = init;
  s.portalDebt[_id] = backing;
  s.portalFeeDebt[_id] = fee;

  vm.mockCall(s.aavePool, abi.encodeWithSelector(IAavePool.backUnbacked.selector), abi.encode(true));
  vm.prank(router);
  this.repayAavePortal(_local, backing, fee, init - 0.5 ether, _id);

  // balance > init => underflow
  require(s.routerBalances[router][_local] > init);
}
```

## Recommendation

After the call to `swapFromLocalAssetIfNeededForExactOut()` you should add the following check:

```solidity
if (_local == adopted) {
    require(routerBalance >= amountIn);
}
```

[connext/nxtp@ac95c1b](https://github.com/connext/nxtp/pull/1450/commits/ac95c1b987c34862e106fc7d643fb8bb7ebb053e)

This is entirely valid and a really severe issue. If the local asset is the adopted asset, `AssetLogic.swapFromLocalAssetIfNeededForExactOut()` will return `amountIn == totalAmount`. So in order to overflow `routerBalances`, the router just needs to provide `_backingAmount + _feeAmount` inputs that sum to exceed the router’s current balance.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the `repayAavePortal` function of the PortalFacet contract. The function is intended to allow a router to repay an Aave loan by swapping a local asset into the adopted asset and then decrementing the router's stored balance. The root cause is the use of an unchecked subtraction on the router's balance after a swap operation that can return a user‑controlled amount. When the local asset passed to the function is the same as the adopted asset, the helper `AssetLogic.swapFromLocalAssetIfNeededForExactOut` short‑circuits and returns the exact `totalAmount` (the sum of `_backingAmount` and `_feeAmount`) as `amountIn`. Because the contract only checks that `routerBalance` is greater than or equal to `_maxIn`, an attacker can pass a `totalAmount` that exceeds the actual router balance, causing `amountIn` to be larger than the stored balance. The subsequent unchecked line `s.routerBalances[msg.sender][_local] -= amountIn;` then underflows, wrapping around the unsigned integer and resulting in an arbitrarily large positive balance for the attacker. This can be exploited by calling `repayAavePortal` with `_local` set to the adopted asset, providing `_backingAmount` and `_feeAmount` that together exceed the router's current balance, and setting `_maxIn` high enough to pass the initial sanity check. The impact is that the attacker’s router balance inflates without depositing any assets, breaking the protocol’s accounting invariants and potentially allowing the attacker to withdraw the artificially created funds. The issue occurs only when the local and adopted assets are identical and the subtraction is performed in an unchecked context, a condition that is not obvious from the external UI and may go unnoticed because the function appears to succeed without error. It was discovered during a manual audit that traced the flow of values from the swap helper back to the balance update and noted the lack of safe arithmetic. The bug belongs to the class of unchecked arithmetic underflow/overflow vulnerabilities, often manifested as “balance inflation” or “credit injection”. From a user’s perspective the router balance may suddenly jump to a very high number, contrary to the expectation that the balance would decrease by the amount repaid. To remediate, the contract should verify that the router’s balance is at least `amountIn` after the swap and before the subtraction, or perform the subtraction with checked arithmetic, ensuring that an underflow cannot occur. Adding a condition such as `require(routerBalance >= amountIn);` after the swap resolves the flaw and restores the intended accounting behavior.

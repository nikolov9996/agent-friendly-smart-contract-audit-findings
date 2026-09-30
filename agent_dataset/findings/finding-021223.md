---
id: 21223
severity: "High"
---

# Overflow in `CollateralTracker` allows minting shares for free

## Description

Malicious actors can mint huge amounts of shares for free and then withdraw all collateral.

## Proof of Concept

```solidity
function previewMint(uint shares) public view returns (uint assets) {
 unchecked {
 assets = Math.mulDivRoundingUp(
 shares * DECIMALS, totalAssets(), totalSupply * (DECIMALS - COMMISSION_FEE)
 );
 }
}

function mint(uint shares, address receiver) external returns (uint assets) {
 assets = previewMint(shares);
 if (assets > type(uint104).max) revert Errors.DepositTooLarge();
 ...
}
```
Insert the following snippet to ColalteralTracker.t.sol for coded PoC:
```solidity
function test_poc1(uint256 x) public {
 _initWorld(x);
 _grantTokens(Bob);

 vm.startPrank(Bob);

 uint shares = type(uint).max / 10000 + 1;
 IERC20Partial(token0).approve(address(collateralToken0), type(uint256).max);
 uint256 returnedAssets0 = collateralToken0.mint(shares, Bob);

 assertEq(shares, collateralToken0.balanceOf(Bob));
 assertEq(returnedAssets0, 1);
}
```

## Recommendation

Remove unchecked block.
```solidity
function maxMint(address) external view returns (uint maxShares) {
 return (convertToShares(type(uint104).max) * DECIMALS) / (DECIMALS + COMMISSION_FEE);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow in the CollateralTracker contract that occurs inside an unchecked block when calculating the amount of underlying assets that correspond to a requested number of shares. The root cause is the use of an unchecked multiplication (shares * DECIMALS) without protecting against overflow, combined with a custom mulDivRoundingUp function that assumes the intermediate product fits into the uint256 range. When an attacker supplies an extremely large share amount, the multiplication wraps around, producing a much smaller product. Consequently the previewMint function returns an asset value that is far lower than the true value of the minted shares – often as low as one unit – while the mint function only checks that the returned asset amount does not exceed type(uint104).max. Because the overflowed asset value passes this check, the contract mints a huge number of shares for essentially no collateral. An attacker can then call the withdrawal logic to claim the full underlying collateral against the artificially inflated share balance, effectively draining the pool. The impact is that funds belonging to honest users can be stolen, leading to a total loss of collateral for the protocol. The condition occurs whenever the mint function is called with a share amount large enough to cause the multiplication to overflow, which is possible because the contract does not enforce an upper bound on the share input before the unchecked block. The affected parties are all users who deposit collateral, the protocol’s economic model, and any token holders relying on the share‑to‑asset accounting. The issue was discovered during a formal audit when the auditors crafted a proof‑of‑concept test that minted shares using type(uint).max/10000+1 and observed that the returned asset amount was only one, while the share balance increased by the full amount. The bug is subtle because the overflow happens inside a low‑level arithmetic routine and the contract still reports a successful mint, making it easy to miss during casual testing. To remediate, the unchecked block should be removed or replaced with safe arithmetic that checks for overflow, and the previewMint calculation should enforce that the share input cannot cause the intermediate product to exceed the maximum representable value. In broader terms, this is a classic unchecked overflow leading to a mis‑calculation of token accounting, allowing free minting of shares and subsequent unauthorized withdrawal of assets, violating the protocol’s accounting invariants and user expectations that each minted share is backed by a proportional amount of collateral.

---
id: 25442
severity: "Low/Info"
---

# midnight parameter in MidnightBundles could be set in the constructor

## Description



## Proof of Concept

## Vulnerability Detail

The bundler uses the supplied `midnight` for three operations in the same call:

1. The auth gate: `IMidnight(midnight).isAuthorized(taker, msg.sender)`.
2. Approval: `_forceApproveMax(token, midnight)`.
3. External dispatch: `IMidnight(midnight).take(...)` / `repay` / `supplyCollateral` / `withdrawCollateral`.

A phishing frontend, malicious SDK, or compromised wallet induces the victim to call the bundler with `midnight = EvilMidnight`, and allows token theft bypassing the checks above.

## Impact

Theft of all tokens pulled in a single call, bounded by the user's signed permit amount or approval.

## Code Snippet

[https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L306-L326](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L306-L326>)

For example:

```solidity
function repayAndWithdrawCollateral(
    address midnight,
    Market memory market,
    uint256 assets,
    address onBehalf,
    TokenPermit memory loanTokenPermit,
    ...
) external {
    require(onBehalf == msg.sender || IMidnight(midnight).isAuthorized(onBehalf, msg.sender), Unauthorized());
    ...
    _pullToken(loanToken, msg.sender, assets, loanTokenPermit);
    _forceApproveMax(loanToken, midnight);

    IMidnight(midnight).repay(market, units, onBehalf, address(0), "");
    ...
}
```

The same pattern repeats at lines [38](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L38>), [106](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L106>), [170](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L170>), and [243](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/periphery/MidnightBundles.sol#L243>).

## Recommendation

Hardcode `midnight` as an `immutable` set in the constructor and remove the parameter from every external function. This mirrors how `EcrecoverRatifier` already pins its `MIDNIGHT`:

```solidity
address public immutable MIDNIGHT;

constructor(address midnight) {
    MIDNIGHT = midnight;
}
```

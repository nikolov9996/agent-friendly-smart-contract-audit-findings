---
id: 25305
severity: "Low/Info"
---

# Documentation inconsistencies

## Description

- The owner of redeem(), withdraw(), removeShares(), requestRedeem() and requestWithdraw() must be allowed and transfer(), transferFrom() check the sender of the shares now.
- setPendingPoolDelegate() in PoolManager can be performed by the operational admin, but is not in the [docs](<https://github.com/maple-labs/maple-core-v2-private/wiki/Globals-Update-%E2%80%90-Q4-Release>).
- Partial redemptions are not allowed due to lack of liquidity in the queue MapleWithdrawalManager [docs](<https://github.com/maple-labs/maple-core-v2-private/wiki/Withdrawal-Manager-Queue-Module-%E2%80%90-Q4-Release#partial-redemptions>).
- IMapleWithdrawalManager.sol - [line 79](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/v1.0.0-rc.0/contracts/interfaces/IMapleWithdrawalManager.sol#L79>) "NOTE: The shares value is ignored.". How it is ignored ? It is used to compute the resultingAssets.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.

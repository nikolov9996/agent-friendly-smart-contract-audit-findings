---
id: 25308
severity: "Low/Info"
---

# Allow lenders to set a minimum amount of asset they would take for their shares

## Description

In the queue-based version of the [withdrawal manager](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/v1.0.0-rc.0/contracts/MapleWithdrawalManager.sol>), lenders don't control when they leave the protocol, so they don't choose when the conversion from shares to asset is performed, which may lead lenders to receive much less asset than they anticipated, since the conversion rate might have decreased substantially while they were waiting for the redeemer to process their redemption.

A particularly detrimental scenario for lenders is if they ask to redeem their shares, and then the pool delegate decides to impair a loan, followed by a call to process redemptions.

In this scenario, the loan impairment would result in a steep increase of the unrealized losses, resulting in the lenders getting much less assets than they were expecting when they asked to redeem their shares, and all of this was outside the lenders' control. Note: if a lender chooses to perform a manual exit they can circumvent this problem.

## Proof of Concept

No PoC provided.

## Recommendation

Allow lenders to set a minimum amount of assets they would be willing to take for their shares (in a way similar to how exchange protocols control for slippage).

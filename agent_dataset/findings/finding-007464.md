---
id: 7464
severity: "High"
---

# Users can avoid liquidation while being under the primary liquidation ratio if on the last short record

## Description

The protocol permits users to maintain up to 254 concurrent short records. When this limit is reached, any additional orders are appended to the final position, rather than creating a new one. A short record is subject to flagging if it breaches the primary liquidation ratio set by the protocol, leading to potential liquidation if it remains below the threshold for a predefined period.

The vulnerability emerges from the dependency of liquidation times on the updatedAt value of shorts. For the last short record, the appending of any new orders provides an alternative pathway for updating the updatedAt value of shorts, enabling users to circumvent liquidation by submitting minimal shorts to block liquidation by adjusting the time difference, thus avoiding liquidation even when they do not meet the collateral requirements for a healthy state.

Let's take a look at the code to see how this works.

Flagging of Short Record:
The flagShort function allows a short to be flagged if it's under primaryLiquidationCR, subsequently invoking setFlagger which updates the short's updatedAt timestamp to the current time.

```solidity
function flagShort(address asset, address shorter, uint8 id, uint16 flaggerHint)
        external
        isNotFrozen(asset)
        nonReentrant
        onlyValidShortRecord(asset, shorter, id)
    {
        // initial code

        short.setFlagger(cusd, flaggerHint);
        emit Events.FlagShort(asset, shorter, id, msg.sender, adjustedTimestamp);
    }
```

Liquidation Eligibility Check:
The _canLiquidate function assesses whether the flagged short is still under primaryLiquidationCR after a certain period and if it's eligible for liquidation, depending on the updatedAt timestamp and various liquidation time frames.

```solidity
function _canLiquidate(MTypes.MarginCallPrimary memory m)
        private
        view
        returns (bool)
    {
       // Initial code

        uint256 timeDiff = LibOrders.getOffsetTimeHours() - m.short.updatedAt;
        uint256 resetLiquidationTime = LibAsset.resetLiquidationTime(m.asset);

        if (timeDiff >= resetLiquidationTime) {
            return false;
        } else {
            uint256 secondLiquidationTime = LibAsset.secondLiquidationTime(m.asset);
            bool isBetweenFirstAndSecondLiquidationTime = timeDiff
                > LibAsset.firstLiquidationTime(m.asset) && timeDiff <= secondLiquidationTime
                && s.flagMapping[m.short.flaggerId] == msg.sender;
            bool isBetweenSecondAndResetLiquidationTime =
                timeDiff > secondLiquidationTime && timeDiff <= resetLiquidationTime;
            if (
                !(
                    (isBetweenFirstAndSecondLiquidationTime)
                        || (isBetweenSecondAndResetLiquidationTime)
                )
            ) {
                revert Errors.MarginCallIneligibleWindow();
            }

            return true;
        }
    }
```

Short Record Merging:
For the last short record, the fillShortRecord function combines new matched shorts with the existing one, invoking the merge function, which updates the updatedAt value to the current time.

```solidity
function fillShortRecord(
        address asset,
        address shorter,
        uint8 shortId,
        SR status,
        uint88 collateral,
        uint88 ercAmount,
        uint256 ercDebtRate,
        uint256 zethYieldRate
    ) internal {
        AppStorage storage s = appStorage();

        uint256 ercDebtSocialized = ercAmount.mul(ercDebtRate);
        uint256 yield = collateral.mul(zethYieldRate);

        STypes.ShortRecord storage short = s.shortRecords[asset][shorter][shortId];
        if (short.status == SR.Cancelled) {
            short.ercDebt = short.collateral = 0;
        }

        short.status = status;
        LibShortRecord.merge(
            short,
            ercAmount,
            ercDebtSocialized,
            collateral,
            yield,
            LibOrders.getOffsetTimeHours()
        );
    }
```

In the merge function we see that we update the updatedAt value to creationTime which is LibOrders.getOffsetTimeHours().

```solidity
function merge(
        STypes.ShortRecord storage short,
        uint88 ercDebt,
        uint256 ercDebtSocialized,
        uint88 collateral,
        uint256 yield,
        uint24 creationTime
    ) internal {
        // Resolve ercDebt
        ercDebtSocialized += short.ercDebt.mul(short.ercDebtRate);
        short.ercDebt += ercDebt;
        short.ercDebtRate = ercDebtSocialized.divU64(short.ercDebt);
        // Resolve zethCollateral
        yield += short.collateral.mul(short.zethYieldRate);
        short.collateral += collateral;
        short.zethYieldRate = yield.divU80(short.collateral);
        // Assign updatedAt
        short.updatedAt = creationTime;
    }
```

This means that even if the position was flagged and is still under the primaryLiquidationCR, it cannot be liquidated as the updatedAt timestamp has been updated, making the time difference not big enough.

<b>Click to expand Proof of Concept</b>

```solidity
    function testShortAvoidLiquidation() public {
        // fill  shorts (up to 254)
        for (uint i; i < 253; i++) {
            fundLimitShortOpt(DEFAULTPRICE, DEFAULTAMOUNT * 5, sender);
            fundLimitBidOpt(DEFAULTPRICE, DEFAULTAMOUNT * 5, receiver);
        } 
        
        // check users last shortrecord
        assertTrue(getShortRecord(sender, 254).status == SR.FullyFilled);

        // price drop
        skipTimeAndSetEth(1 hours, 2000 ether);

        // flag short
        vm.prank(receiver);
        diamond.flagShort(asset, sender, 254, Constants.HEAD);

        // check flag
        assertTrue(getShortRecord(sender, 254).flaggerId == 1);

        // skip time to primary liquidation time
        skipTimeAndSetEth(11 hours, 2000 ether);

        // User matches new min short (added to last spot)
        fundLimitShortOpt(DEFAULTPRICE * 2, DEFAULTAMOUNT  , sender);
        fundLimitBidOpt(DEFAULTPRICE * 2, DEFAULTAMOUNT  , receiver);

        // flagger tries to liquidate short in eligible window
        fundLimitAskOpt(DEFAULTPRICE, DEFAULTAMOUNT * 6, extra);
        vm.startPrank(receiver);
        vm.expectRevert(Errors.MarginCallIneligibleWindow.selector);
        diamond.liquidate(
            asset, sender, 254, shortHintArrayStorage
        );
        vm.stopPrank();
    }
```

This allows a user with a position under the primaryLiquidationCR to avoid primary liquidation even if the short is in the valid time ranges for liquidation.

## Proof of Concept

no poc

## Recommendation

Impose stricter conditions for updating the last short record when the position is flagged and remains under the primaryLiquidationCR post-merge, similar to how the combineShorts function works.

```solidity
function createShortRecord(
        address asset,
        address shorter,
        SR status,
        uint88 collateral,
        uint88 ercAmount,
        uint64 ercDebtRate,
        uint80 zethYieldRate,
        uint40 tokenId
    ) internal returns (uint8 id) {
        AppStorage storage s = appStorage();

        // Initial code

        } else {
            // All shortRecordIds used, combine into max shortRecordId
            id = Constants.SHORTMAXID;
            fillShortRecord(
                asset,
                shorter,
                id,
                status,
                collateral,
                ercAmount,
                ercDebtRate,
                zethYieldRate
            );

            // If the short was flagged, ensure resulting c-ratio > primaryLiquidationCR
            if (Constants.SHORTMAXID.shortFlagExists) {
                if (
                    Constants.SHORTMAXID.getCollateralRatioSpotPrice(
                        LibOracle.getSavedOrSpotOraclePrice(_asset)
                    ) < LibAsset.primaryLiquidationCR(_asset)
                ) revert Errors.InsufficientCollateral();
                // Resulting combined short has sufficient c-ratio to remove flag
                Constants.SHORTMAXID.resetFlag();
            }
        }
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a liquidation‑bypass that arises from the way the protocol updates the timestamp of a short record when the record is merged. Short positions are stored in up to 254 separate records; when this limit is reached any new order is merged into the last record instead of creating a new one. The contract determines whether a flagged short can be liquidated by comparing the current time with the short’s updatedAt field and a series of liquidation windows (first, second and reset periods). When a short is flagged because its collateral‑to‑debt ratio falls below the primary liquidation collateral ratio, the flagShort function records the flagger and updates the short’s updatedAt to the current hour. However, the merge logic used for the last short record also overwrites updatedAt with the time of the merge. An attacker can therefore keep a short that is already under‑collateralized, flag it, and then submit a minimal additional short that is merged into the last slot. This merge refreshes updatedAt, shrinking the time difference used by _canLiquidate and causing the contract to believe the short is still within a non‑eligible window, even though the collateral ratio remains below the required threshold. The exploit works only when the user has filled the maximum number of short records and the flagged short occupies the final slot, because only then does the contract fall back to merging instead of creating a new record. From a user’s perspective the position appears flagged and under‑collateralized, yet liquidators receive a revert (MarginCallIneligibleWindow) and cannot close the position, effectively “freezing” the short and allowing the user to avoid liquidation. This can lead to persistent under‑collateralized debt, harming the protocol’s risk model and exposing liquidators to loss of expected fees. The issue was discovered during a security audit by CodeHawks through systematic testing of the flag‑and‑liquidate flow with the maximum short count. It is subtle because the timestamp update is hidden inside the merge function and the flagging logic does not re‑validate the collateral ratio after a merge, making the problem easy to miss in casual code review. The bug belongs to the class of time‑based liquidation bypasses caused by state mutation that resets eligibility counters. To remediate, the contract should prevent the updatedAt field from being refreshed when a short is flagged and remains under the primary liquidation ratio, or it should enforce a post‑merge collateral‑ratio check that clears the flag only if the combined position satisfies the required ratio, as illustrated in the recommended combineShorts logic.

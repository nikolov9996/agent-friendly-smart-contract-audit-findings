---
id: 7506
severity: "Medium"
---

# Rounding-up of user's `cRatio` causes loss for the protocol

## Description

At multiple places in the code, user's collateral ratio has been calculated in a manner which causes loss of precision (rounding-up) due to division before multiplication. This causes potential loss for the DittoETH protocol, among other problems.

Let's break the issue down into 4 smaller parts:<br>
PART 1:
Let us first look inside getOraclePrice():
```solidity
File: contracts/libraries/LibOracle.sol

20            function getOraclePrice(address asset) internal view returns (uint256) {
21                AppStorage storage s = appStorage();
22                AggregatorV3Interface baseOracle = AggregatorV3Interface(s.baseOracle);
23                uint256 protocolPrice = getPrice(asset);
24                // prettier-ignore
25                (
26                    uint80 baseRoundID,
27                    int256 basePrice,
28                    /*uint256 baseStartedAt*/
29                    ,
30                    uint256 baseTimeStamp,
31                    /*uint80 baseAnsweredInRound*/
32                ) = baseOracle.latestRoundData();
33
34                AggregatorV3Interface oracle = AggregatorV3Interface(s.asset[asset].oracle);
35                if (address(oracle) == address(0)) revert Errors.InvalidAsset();
36
37                if (oracle == baseOracle) {
38                    //@dev multiply base oracle by 10**10 to give it 18 decimals of precision
39                    uint256 basePriceInEth = basePrice > 0
40                        ? uint256(basePrice * Constants.BASEORACLEDECIMALS).inv()
41                        : 0;
42                    basePriceInEth = baseOracleCircuitBreaker(
43                        protocolPrice, baseRoundID, basePrice, baseTimeStamp, basePriceInEth
44                    );
45                return basePriceInEth;
46                } else {
47                    // prettier-ignore
48                    (
49                        uint80 roundID,
50                        int256 price,
51                        /*uint256 startedAt*/
52                        ,
53                        uint256 timeStamp,
54                        /*uint80 answeredInRound*/
55                    ) = oracle.latestRoundData();
56                uint256 priceInEth = uint256(price).div(uint256(basePrice));
57                    oracleCircuitBreaker(
58                        roundID, baseRoundID, price, basePrice, timeStamp, baseTimeStamp
59                    );
60                return priceInEth;
61                }
62            }
```
Based on whether the oracle is baseOracle or not, the function returns either basePriceEth or priceInEth.<br>
basePriceEth can be uint256(basePrice * Constants.BASEORACLEDECIMALS).inv() which is basically 1e36 / (basePrice * Constants.BASEORACLEDECIMALS) or simply written, of the form oracleN / oracleD where oracleN is the numerator with value 1e36 (as defined here) and oracleD is the denominator.<br>
priceInEth is given as uint256 priceInEth = uint256(price).div(uint256(basePrice)) which again is of the form oracleN / oracleD.

<br>

PART 2:
getSavedOrSpotOraclePrice() too internally calls the above getOraclePrice() function, if it has been equal to or more than 15 minutes since the last time LibOrders.getOffsetTime() was set:
```solidity
File: contracts/libraries/LibOracle.sol

153           function getSavedOrSpotOraclePrice(address asset) internal view returns (uint256) {
154               if (LibOrders.getOffsetTime() - getTime(asset) < 15 minutes) {
155                   return getPrice(asset);
156               } else {
157                return getOraclePrice(asset);
158               }
159           }
```

<br>

PART 3:
getCollateralRatioSpotPrice() calculates cRatio as:
```solidity
File: contracts/libraries/LibShortRecord.sol

30            function getCollateralRatioSpotPrice(
31                STypes.ShortRecord memory short,
32                uint256 oraclePrice
33            ) internal pure returns (uint256 cRatio) {
34                return short.collateral.div(short.ercDebt.mul(oraclePrice));
35            }
```

<br>

PART 4 (FINAL PART):
There are multiple places in the code (mentioned below under Impacts section) which compare the user's cRatio to initialCR or LibAsset.primaryLiquidationCR(_asset) in the following manner:
```solidity
if (short.getCollateralRatioSpotPrice(LibOracle.getSavedOrSpotOraclePrice(asset)) < LibAsset.primaryLiquidationCR(asset))
```
Calling short.getCollateralRatioSpotPrice(LibOracle.getSavedOrSpotOraclePrice(asset)) means the value returned from it would be:
```diff
      // @audit-issue : Potential precision loss. Division before multiplication should not be done.
      shortCollateral / (shortErcDebt * (oracleN / oracleD))           // return short.collateral.div(short.ercDebt.mul(oraclePrice));
```
which has the potential for precision loss (rounding-up) due to division before multiplication. The correct style ought to be:
```diff
      (shortCollateral * oracleD) / (shortErcDebt * oracleN)
```
<br>

## Proof of Concept

Have attempted to keep all values in close proximity to the ones present in forked mainnet tests.<br><br>

Let's assume some values for numerator & denominator and other variables:
```solidity
    uint256 private short_collateral = 100361729669569000000; // ~ 100 ether
    uint256 private shortercDebt = 100000000000000000000000; // 100000 ether
    uint256 private price = 99995505; // oracleN
    uint256 private basePrice = 199270190598; // oracleD
    uint256 private primaryLiquidationCR = 2000000000000000000; // 2 ether (as on forked mainnet)

// For this example, we assume that oracle != baseOracle, so that the below calculation would be done by the protocol
So calculated priceInEth = price.div(basePrice) = 501808648347845  // ~ 0.0005 ether
```

<br>

Let's calculate for the scenario of flagShort() where the code logic says:
```solidity
  53                if (
  54                short.getCollateralRatioSpotPrice(LibOracle.getSavedOrSpotOraclePrice(asset))
  55                    >= LibAsset.primaryLiquidationCR(asset)      // @audit-issue : this will evaluate to true, then revert, due to rounding-up and the short will incorrectly escape flagging
  56                ) {
  57                    revert Errors.SufficientCollateral();
  58                }
```

<br>

Create a file named test/IncorrectCRatioCheck.t.sol and paste the following code in it. Some mock functions are included here which mirror protocol's calculation style:
```solidity
// SPDX-License-Identifier: GPL-3.0-only
pragma solidity 0.8.21;

import {U256} from "contracts/libraries/PRBMathHelper.sol";
import {OBFixture} from "test/utils/OBFixture.sol";
import {console} from "contracts/libraries/console.sol";

contract IncorrectCRatioCheck is OBFixture {
    using U256 for uint256;

    uint256 private short_collateral = 85307470219133700000; // ~ 85.3 ether
    uint256 private shortercDebt = 100000000000000000000000; // 100000 ether
    uint256 private price = 99995505; // oracleN
    uint256 private basePrice = 199270190598; // (as on forked mainnet)  // oracleD
    uint256 private primaryLiquidationCR = 1700000000000000000; // 1.7 ether (as on forked mainnet)

    function _getSavedOrSpotOraclePrice() internal view returns (uint256) {
        uint256 priceInEth = price.div(basePrice);
        return priceInEth; // will return 501808648347845 =~ 0.0005 ether  // (as on forked mainnet)
    }

    function getCollateralRatioSpotPriceIncorrectStyleAsInExisting_DittoProtocol(
        uint256 oraclePrice
    ) internal view returns (uint256) {
        return short_collateral.div(shortercDebt.mul(oraclePrice));
    }

    function getCollateralRatioSpotPrice_CorrectStyle(uint256 oracleN, uint256 oracleD)
        internal
        view
        returns (uint256)
    {
        return (short_collateral.mul(oracleD)).div(shortercDebt.mul(oracleN));
    }

    /* solhint-disable no-console */
    function testGetCollateralRatioSpotPriceIncorrectStyleAsInExistingDittoProtocol(
    ) public view {
        uint256 cRatio =
        getCollateralRatioSpotPriceIncorrectStyleAsInExisting_DittoProtocol(
            _getSavedOrSpotOraclePrice()
        );
        console.log("cRatio calculated (existing style) =", cRatio);
        if (cRatio >= primaryLiquidationCR) {
            console.log("Errors.SufficientCollateral; can not be flagged");
        } else {
            console.log("InsufficientCollateral; can be flagged");
        }
    }

    /* solhint-disable no-console */
    function testGetCollateralRatioSpotPriceCorrectStyle() public view {
        uint256 cRatio = getCollateralRatioSpotPrice_CorrectStyle(price, basePrice);
        console.log("cRatio calculated (correct style) =", cRatio);
        if (cRatio >= primaryLiquidationCR) {
            console.log("Errors.SufficientCollateral; can not be flagged");
        } else {
            console.log("InsufficientCollateral; can be flagged");
        }
    }
}
```
 
<br>
First, let's see the output as per protocol's calculation. Run forge test --mt testGetCollateralRatioSpotPriceIncorrectStyleAsInExistingDittoProtocol -vv:
```solidity
Logs:
  cRatio calculated (existing style) = 1700000000000000996
  Errors.SufficientCollateral; can not be flagged
```

So the short can not be flagged as cRatio > primaryLiquidationCR of 1700000000000000000.
<br>
<br>
Now, let's see the output as per the correct calculation. Run forge test --mt testGetCollateralRatioSpotPriceCorrectStyle() -vv:
```solidity
Logs:
  cRatio calculated (correct style) = 1699999999999899995
  InsufficientCollateral; can be flagged
```

Short's cRatio is actually below primaryLiquidationCR. Should have been flagged ideally.

<br>

## Recommendation

These steps need to be taken to fix the issue. Developer may have to make some additional changes since .mul, .div, etc are being used from the PRBMathHelper.sol library. Following is the general workflow required:<br>
Create additional functions to fetch oracle parameters instead of price: Create copies of getOraclePrice() and getSavedOrSpotOraclePrice(), but these ones return oracleN & oracleD instead of the calculated price. Let's assume the new names to be getOraclePriceParams() and getSavedOrSpotOraclePriceParams().
Create a new function to calculate cRatio which will be used in place of the above occurences of getCollateralRatioSpotPrice(): 
```solidity
    function getCollateralRatioSpotPriceFromOracleParams(
        STypes.ShortRecord memory short,
        uint256 oracleN,
        uint256 oracleD
    ) internal pure returns (uint256 cRatio) {
        return (short.collateral.mul(oracleD)).div(short.ercDebt.mul(oracleN));
    }
```
<br>
For fixing the last issue of oraclePrice.mul(1.01 ether) on L847, first call getOraclePriceParams() to get oracleN & oracleD and then:
```diff
  845                       //@dev: force hint to be within 1% of oracleprice
  846                       bool startingShortWithinOracleRange = shortPrice
847                           <= (oracleN.mul(1.01 ether)).div(oracleD)
  848                           && s.shorts[asset][prevId].price >= oraclePrice;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision loss in the calculation of a user’s collateral ratio (cRatio) caused by performing division before multiplication when converting the oracle price fraction. The protocol obtains the oracle price as a fraction oracleN/oracleD (where oracleN is a large numerator and oracleD is the denominator). The existing function computes cRatio as collateral.div(debt.mul(oracleN.div(oracleD))) which effectively evaluates collateral / (debt * (oracleN / oracleD)). Because the division of oracleN by oracleD is executed first, integer division truncates the result and rounds it up, inflating the denominator and making the resulting cRatio appear larger than it truly is. This mis‑calculation can allow a position that is actually under‑collateralised to be considered sufficiently collateralised, preventing liquidation or flagging. The issue appears whenever the protocol checks a short position against the primary liquidation collateral ratio, for example in flagShort() or liquidation logic, and only when the oracle price is derived from a non‑base oracle (i.e., when priceInEth = price.div(basePrice)). It affects any user who opens a short position, the protocol’s risk parameters, and ultimately the funds that should be liquidated to protect lenders. The bug was discovered during a manual audit that traced the flow from getOraclePrice through getSavedOrSpotOraclePrice to getCollateralRatioSpotPrice, noticing the division‑before‑multiplication pattern. The problem is subtle because the numbers involved are large and the rounding error may be only a few wei, yet it can flip the comparison result around the liquidation threshold. Exploiting the bug requires opening a position with values that place the true cRatio just below the liquidation limit; the rounded‑up calculation will push it above the limit, causing the contract to skip the liquidation step and allowing the attacker to keep the position open and potentially profit from adverse price movements. From the user’s perspective the contract may report a healthy collateral ratio, the position is not flagged for liquidation, and the user may see “insufficient collateral” messages disappear unexpectedly. The impact is a loss of protocol safety: under‑collateralised positions remain active, exposing the protocol to bad debt and reducing confidence of lenders. The issue is a classic example of integer‑math precision loss, often classified as a rounding‑up bug in financial calculations. To fix the problem the calculation should be rearranged to multiply the collateral by the denominator before dividing by the product of debt and numerator, i.e., (collateral.mul(oracleD)).div(debt.mul(oracleN)). This can be implemented by exposing the oracle numerator and denominator separately and using a dedicated helper that respects the PRBMath library’s safe‑math functions. After the change the cRatio will be computed with full precision, the comparison against the liquidation threshold will be accurate, and positions will be correctly flagged or liquidated, restoring the intended risk controls.

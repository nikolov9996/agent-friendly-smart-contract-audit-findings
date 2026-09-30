---
id: 3536
severity: "High"
---

# LibUsdOracle will compromise Beanstalk peg due to wrong price and DoS

## Description

The function getUsdPrice from LibUsdOracle should return the token value in USD. For example, one of its consumers is the function getMintFertilizerOut:

fertilizerAmountOut = tokenAmountIn.div(LibUsdOracle.getUsdPrice(barnRaiseToken));

The goal of this function is to return the fertilizer amount with 0 decimals, therefore if the WETH value is at $1000 and the user would provide 1 WETH:

tokenAmountIn = 1e18.div(1e15) = 1e3 = 1000

Another critical use case for getUsdPrice is: fetching the ratios to calculate the deltaB.

```solidity
function getRatiosAndBeanIndex(
        IERC20[] memory tokens,
        uint256 lookback
    ) internal view returns (uint[] memory ratios, uint beanIndex, bool success) {
        success = true;
        ratios = new uint[](tokens.length);
        beanIndex = type(uint256).max;
        for (uint i; i < tokens.length; ++i) {
            if (C.BEAN == address(tokens[i])) {
                beanIndex = i;
                ratios[i] = 1e6;
            } else {
                ratios[i] = LibUsdOracle.getUsdPrice(address(tokens[i]), lookback); // @audit expect value return in USD
                if (ratios[i] == 0) {
                    success = false;
                }
            }
        }
        require(beanIndex != type(uint256).max, "Bean not in Well.");
    }
```

The function getRatiosAndBeanIndex is used throughout the system, including in processes like Sunrise and Convert, to help Bean maintain its peg.
The first issue is that the price returned by getUsdPrice will be incorrect for tokens that use "external oracle" due to the duplicated division using 1e24.

```solidity
// getUsdPrice
        uint256 tokenPrice = getTokenPriceFromExternal(token, lookback);
        if (tokenPrice == 0) return 0;
        return uint256(1e24).div(tokenPrice);

// getTokenPriceFromExternal

// returns uint256(1e24).div(result from chainlink with 6 decimals)
            return
                uint256(1e24).div(
                    LibChainlinkOracle.getTokenPrice(
                        chainlinkOraclePriceAddress,
                        LibChainlinkOracle.FOURHOURTIMEOUT,
                        lookback
                    )
                );
```

This will result in an inaccurate price. For example, when the price of WBTC is $50,000, it will return 50000e6 instead of the correct value 2e13. This discrepancy will cause Beanstalk to consider an erroneous ratio, resulting in an incorrect DeltaB.

Beanstalk uses deltaB to determine:
Whether the system is Above or below the peg
Sow and Pods (issuing debt)
Flood
Convert

In a nutshell, all components from Beanstalk will be affected by DeltaBs originating from tokens using Oracle with encodedType 0x01. 
The second issue is that the getTokenPriceFromExternal doesn't check for the return from the Oracle value before div:

```solidity
return
                uint256(1e24).div(
                    LibChainlinkOracle.getTokenPrice(
                        chainlinkOraclePriceAddress,
                        LibChainlinkOracle.FOURHOURTIMEOUT,
                        lookback
                    )
                );
```

When the Chainlink Oracle fails to fetch the price it returns 0. Hence, the function will revert due to uint256(1e24).div(0).

High.
Incorrect price: This will compromise the entire system, as all peg-related components, including Sunrise and Convert, depend on the price.
DoS: Sunrise will revert and disrupt all other components that rely on the price. The risk of a DoS is increased due to stepOracle calling multiple tokens (instead of one as previously) to fetch their prices, raising the chances of an Oracle failure.

## Proof of Concept

For the incorrect price:

Add the following test on oracle.t.sol

```solidity
function testgetUsdPricewhenExternalToken_priceIsInvalid() public {
        // pre condition: encode type 0x01 

        // WETH price is 1000
        uint256 priceWETH = OracleFacet(BEANSTALK).getUsdPrice(C.WETH);
        assertEq(priceWETH, 1e15);  //  1e18/1e3 = 1e15

        // WBTC price is 50000
        uint256 priceWBTC = OracleFacet(BEANSTALK).getUsdPrice(WBTC);
        assertEq(priceWBTC, 2e13); // 1e24.div(50000e6) = 2e13
    }
```

Run: forge test --match-test testgetUsdPricewhenExternalToken_priceIsInvalid

Output:

```javascript
Failing tests:
Encountered 1 failing test in test/foundry/silo/oracle.t.sol:OracleTest
[FAIL. Reason: assertion failed: 50000000000 != 20000000000000] testgetUsdPricewhenExternalToken_priceIsInvalid() (gas: 64594)
```

For the DoS when Chainlink oracle returns 0:
Add this test on oracle.t.sol

```solidity
// first - import {MockChainlinkAggregator} from "contracts/mocks/chainlink/MockChainlinkAggregator.sol";

function testgetUsdPricewillDoS_whenOracleFail() public { 
        // pre condition: encode type 0x01 and oracle fail
        MockChainlinkAggregator(WBTCUSDCHAINLINKPRICEAGGREGATOR).setOracleFailure();

        // action
        vm.expectRevert();
        OracleFacet(BEANSTALK).getUsdPrice(WBTC);
    }
```

Run: forge test --match-test testgetUsdPricewillDoS_whenOracleFail

Output:

```javascript
Ran 1 test for test/foundry/silo/oracle.t.sol:OracleTest
[PASS] testgetUsdPricewillDoS_whenOracleFail() (gas: 21500)
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 259.13ms
```

## Recommendation

To fix both issues: On getTokenPriceFromExternal return the price from Chainlink directly, instead of scaling it.

```diff
return LibChainlinkOracle.getTokenPrice(
                        chainlinkOraclePriceAddress,
                        LibChainlinkOracle.FOURHOURTIMEOUT,
                        lookback
                    );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the price‑oracle helper used by the Beanstalk protocol to obtain a token's value in USD. The function that should return a USD price performs two successive scalings by 1e24: it first divides the Chainlink price (which already has 6 decimals) by 1e24, and then the caller divides 1e24 by that result. This double division inflates the returned price for any token that relies on an external oracle (encoded type 0x01). For example, a real WBTC price of $50,000 is reported as 5 × 10^10 instead of the correct 2 × 10^13, causing the protocol to compute a wildly inaccurate ratio. The inaccurate ratio propagates to the deltaB calculation, which determines whether the system is above or below the peg, how much fertilizer can be minted, and how conversion and sunrise operations behave. Consequently users may see zero fertilizer minted, conversion amounts that are far off, or sunrise transactions that revert, effectively breaking the peg and disrupting the entire economic model. A second flaw appears because the helper does not verify that the Chainlink call returned a non‑zero price before performing the division. When the oracle fails and returns 0, the division by zero triggers a revert, allowing an attacker or a simple oracle outage to cause a denial‑of‑service on any function that queries the price, such as sunrise or convert. The issue is triggered whenever a token using an external oracle is processed, which includes many core assets in the system. It was discovered during a formal audit when unit tests compared expected USD prices against the contract’s output and observed both an inflated value and a revert on simulated oracle failure. The bug is subtle because the contract still returns a numeric value, so the error can go unnoticed until the peg drifts or a transaction fails. To remediate, the price helper should return the raw Chainlink price without the extra 1e24 scaling and must explicitly check for a zero result before any division, reverting with a clear error message if the oracle provides no data. This correction restores accurate deltaB calculations, preserves the peg, and eliminates the possibility of a price‑related DoS.

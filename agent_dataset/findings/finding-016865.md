---
id: 16865
severity: "High"
---

# Incorrect handling of `pricefeed.decimals`

## Description

Wrong math for handling pricefeed decimals. This code will only work for pricefeeds of 8 decimals, any others give wrong/incorrect data. The maths used can be shown in three lines:

```solidity
nowPrice = (price1 * 10000) / price2;
nowPrice = nowPrice * int256(10**(18 - priceFeed1.decimals()));
return nowPrice / 1000000;
```

Line1: adds 4 decimals  
Line2: adds (18 - d) decimals, (where d = pricefeed.decimals())  
Line3: removes 6 decimals

Total: adds (16 - d) decimals

when d=8, the contract correctly returns an 8 decimal number. However, when d = 6, the function will return a 10 decimal number. This is further raised by (18-d = 12) decimals when checking for depeg event, leading to a 22 decimal number which is 4 orders of magnitude incorrect.

if d=18, (like usd-eth pricefeeds) contract fails / returns 0.

All chainlink contracts which give price in eth, operate with 18 decimals. So this can cripple the system if added later.

## Proof of Concept

Running the test AssertTest.t.sol:testPegOracleMarketCreation and changing the line on

to

```solidity
PegOracle pegOracle3 = new PegOracle(
            0xB1552C5e96B312d0Bf8b554186F846C40614a540,  //usd-eth contract address
            btcEthOracle
        );
```

gives this output

```
oracle3price1: 1085903802394919427
oracle3price2: 13753840915281064000
oracle3price1 / oracle3price2: 0
```

returning an oracle value of 0. Simulating with a mock price feed of 6 decimals gives results 4 orders of magnitude off.

## Recommendation

Since only the price ratio is calculated, there is no point in increasing the decimal by (18-d) in the second line. Proposed solution:

```solidity
nowPrice = (price1 * 10000) / price2;
nowPrice = nowPrice * int256(10**(priceFeed1.decimals())) * 100;
return nowPrice / 1000000;
```

This returns results in d decimals, no matter the value of d.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect handling of the decimal precision supplied by external price feed contracts. The affected function computes a price ratio by first multiplying two raw feed values, then scaling the intermediate result with a factor based on the feed’s declared number of decimals, and finally dividing by a constant. The scaling logic assumes that the feed always returns values with eight decimal places; it adds four decimals, then adds a further (18‑d) decimals where d is the feed’s decimals, and finally removes six decimals. When d equals eight the net scaling is zero and the function returns a correctly formatted eight‑decimal price. However, if the feed uses a different precision – for example six decimals – the net scaling becomes +2 decimals, causing the function to output a price that is two orders of magnitude larger than it should be. In the extreme case of a feed with eighteen decimals (such as ETH‑based Chainlink feeds) the net scaling becomes –12 decimals, resulting in a division that under‑flows to zero. The root cause is the hard‑coded arithmetic that mixes fixed decimal adjustments with a dynamic term that is incorrectly derived from the feed’s decimals, rather than using the ratio’s inherent precision. An attacker, or even an honest protocol participant, can exploit this by supplying a price feed with a non‑standard decimal count, which makes the oracle return wildly inflated or deflated prices. This broken price can be used by downstream logic that relies on the oracle for liquidation thresholds, margin checks, or de‑peg detection; consequently trades may be executed at incorrect rates, liquidations may trigger erroneously, or de‑peg events may be missed, leading to potential loss of collateral or funds. The condition occurs whenever the contract is instantiated with a price feed that does not have eight decimals, which includes many Chainlink feeds that provide eight‑decimal BTC‑USD prices but also eighteen‑decimal ETH‑USD feeds. The affected parties are the protocol itself, its liquidity providers, borrowers, and any user who depends on accurate price data for making financial decisions. The issue was discovered during a formal audit when a test case that instantiated the oracle with a USD‑ETH feed (eighteen decimals) returned a price of zero, and a mock feed with six decimals produced values four orders of magnitude too high. The bug is subtle because the contract does return a numeric value, so a simple sanity check may not reveal the scaling error; only careful inspection of the decimal handling or comparison with known feed precisions exposes the problem. To remediate the flaw, the calculation should avoid the unnecessary (18‑d) scaling term and instead apply a deterministic factor that preserves the original feed precision, for example multiplying by 10**d and by the constant 100, then normalising by the same divisor, ensuring the output always carries the same number of decimals as the input feed regardless of d. By correcting the arithmetic, the oracle will return accurate prices, preserving the protocol’s economic assumptions and preventing mis‑priced transactions or erroneous liquidations.

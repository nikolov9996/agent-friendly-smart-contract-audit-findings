---
id: 19135
severity: "High"
---

# Improper precision of strike price calculation can result in broken protocol

## Description

Due to a lack of adequate precision, the calculated strike price for a PUT option for rDPX is not guaranteed to be 25% OTM, which breaks core assumptions around (1) protecting downside price movement of the rDPX which makes up part of the collateral for dpxETH & (2) not overpaying for PUT option protection.

More specifically, the price of rDPX as used in the `calculateBondCost` function of the RdpxV2Core contract is represented as ETH / rDPX, and is given in 8 decimals of precision. To calculate the strike price which is 25% OTM based on the current price, the logic calls the `roundUp` function on what is effectively 75% of the current spot rDPX price. The issue is with the `roundUp` function of the PerpetualAtlanticVault contract, which effectively imposes a minimum value of 1e6.

Considering approximate recent market prices of `$`2000/ETH and `$`20/rDPX, the current price of rDPX in 8 decimals of precision would be exactly 1e6. Then to calculate the 25% OTM strike price, we would arrive at a strike price of `1e6 * 0.75 = 75e4`. The `roundUp` function will then round up this value to `1e6` as the strike price, and issue the PUT option using that invalid strike price. Obviously this strike price is not 25% OTM, and since its an ITM option, the premium imposed will be significantly higher. Additionally this does not match the implementation as outlined in the docs.

## Proof of Concept

When a user calls the `bond` function of the RdpxV2Core contract, it will calculate the `rdpxRequired` and `wethRequired` required by the user in order to mint a specific `_amount` of dpxETH, which is calculated using the `calculateBondCost` function:

```solidity
function bond(
  uint256 _amount,
  uint256 rdpxBondId,
  address _to
) public returns (uint256 receiptTokenAmount) {
  _whenNotPaused();
  // Validate amount
  _validate(_amount > 0, 4);

  // Compute the bond cost
  (uint256 rdpxRequired, uint256 wethRequired) = calculateBondCost(
    _amount,
    rdpxBondId
  );
  ...
}
```

Along with the collateral requirements, the `wethRequired` will also include the ETH premium required to mint the PUT option. The amount of premium is calculated based on a strike price which represents 75% of the current price of rDPX (25% OTM PUT option). In the `calculateBondCost` function:

```solidity
function calculateBondCost(
  uint256 _amount,
  uint256 _rdpxBondId
) public view returns (uint256 rdpxRequired, uint256 wethRequired) {
  uint256 rdpxPrice = getRdpxPrice();

  ...

  uint256 strike = IPerpetualAtlanticVault(addresses.perpetualAtlanticVault)
    .roundUp(rdpxPrice - (rdpxPrice / 4)); // 25% below the current price

  uint256 timeToExpiry = IPerpetualAtlanticVault(
    addresses.perpetualAtlanticVault
  ).nextFundingPaymentTimestamp() - block.timestamp;
  if (putOptionsRequired) {
    wethRequired += IPerpetualAtlanticVault(addresses.perpetualAtlanticVault)
      .calculatePremium(strike, rdpxRequired, timeToExpiry, 0);
  }
}
```

As shown, the strike price is calculated as:

```solidity
uint256 strike = IPerpetualAtlanticVault(addresses.perpetualAtlanticVault).roundUp(rdpxPrice - (rdpxPrice / 4));
```

It uses the `roundUp` function of the PerpetualAtlanticVault contract which is defined as follows:

```solidity
function roundUp(uint256 _strike) public view returns (uint256 strike) {
  uint256 remainder = _strike % roundingPrecision;
  if (remainder == 0) {
    return _strike;
  } else {
    return _strike - remainder + roundingPrecision;
  }
}
```

In this contract `roundingPrecision` is set to `1e6`, and this is where the problem arises. As I mentioned earlier, take the following approximate market prices: `$`2000/ETH and `$`20/rDPX. This means the `rdpxPrice`, which is represented as ETH/rDPX in 8 decimals of precision, will be `1e6`. To calculate the strike price, we get the following: `1e6 * 0.75 = 75e4`. However this value is fed into the `roundUp` function which will convert the `75e4` to `1e6`. This value of `1e6` is then used to calculate the premium, which is completely wrong. Not only is `1e6` not 25% OTM, but it is actually ITM, meaning the premium will be significantly higher than was intended by the protocol design.

## Recommendation

The value of the `roundingPrecision` is too high considering reasonable market prices of ETH and rDPX. Consider decreasing it.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision loss in the calculation of the strike price for a PUT option on the rDPX token. The protocol is supposed to set the strike 25 % below the current market price (an out‑of‑the‑money, OTM, option) so that users only pay a modest premium for downside protection. The price of rDPX is stored as ETH per rDPX with eight decimal places, and the contract computes the strike by taking 75 % of this price and then passing the result to a generic roundUp function. The roundUp function uses a constant roundingPrecision of 1 e6, which is far larger than the granularity of the price representation. When the spot price is around 1 e6 (approximately $20 per rDPX given typical ETH prices), the 75 % value becomes 75 e4. Because the remainder of 75 e4 divided by 1 e6 is non‑zero, roundUp adds the roundingPrecision and returns 1 e6 instead of the intended 75 e4. Consequently the strike price is rounded up to the full spot price, turning the option from OTM into in‑the‑money (ITM). The premium calculation then uses this inflated strike, causing users to pay a significantly higher ETH premium than expected. The bug manifests whenever the rDPX price, expressed with eight decimals, is close to the roundingPrecision threshold, which is a realistic scenario given current market values. It affects any user who calls the bond function to mint dpxETH, because the bond cost includes the premium for the PUT option; users see higher required WETH, experience unexpected loss of funds, and the protocol’s economic assumptions about protection cost are broken. The issue was discovered during a formal audit by Code4rena when the auditors examined the calculateBondCost logic and the roundUp implementation. It is hard to notice because the rounding function appears innocuous and the price values look plausible; only under specific price ranges does the strike become ITM, leading to over‑payment that may not be immediately obvious from the UI. The vulnerability belongs to the class of fixed‑point rounding errors in financial smart contracts, where coarse rounding precision causes loss of intended economic behavior. To remediate, the roundingPrecision should be reduced to a value that matches the price granularity, or the rounding logic should be redesigned to avoid upward rounding that can push an OTM strike into ITM territory, thereby restoring the correct premium calculation and preserving the protocol’s intended risk profile.

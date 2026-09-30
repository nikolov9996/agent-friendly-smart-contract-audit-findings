---
id: 6421
severity: "High"
---

# Broken mint if market pre-mint less than p

## Description

When market is created, it is allowed that params.premint and the p configured inside params.curveParameters is different, as long as params.premint is lower and result in 0 when provided to getBuyPrice.
```solidity
function checkParameters(MarketParameters memory params) public view virtual {
    if (!trustedCurves[address(params.priceCurve)]) {
        revert UntrustedCurve();
    }
    // reverts if parameters are out of sanity range
    params.priceCurve.checkParameters(params.curveParameters, params.fundingGoal);
    //the "premint" parameter can be different from the curve's premint parameter
    if (params.priceCurve.getBuyPrice(0, params.premint, params.curveParameters) != 0) {
        revert ParameterMismatch();
    }
    // check that the deadline isn't too far in the future
    //(eg millisecond issues)
    if (params.deadline > block.timestamp + 10 * 365 days) {
        revert ParameterMismatch();
    }
}
```
However, when mint is called, it will check against params.premint, which is not correct and will cause issue if the actual p parameter is greater than params.premint.
```solidity
function mint(uint256 tokenId, uint256 amount)
    external
    payable
    nonReentrant
    returns (uint256 gross, uint256 net, uint256 tokensToMint)
{
    MarketData storage market = markets[tokenId];
    if (market.state != MarketState.OPEN) {
        revert BadState(MarketState.OPEN, market.state);
    }
    MarketParameters memory _marketParams = marketParams[tokenId];
    if (trySettle(tokenId) > MarketState.OPEN) {
        //this allows settling the market implicitly without reverting
        Address.sendValue(payable(_msgSender()), msg.value);
        return (0, 0, 0);
    }
    uint256 tradingFee;
    //when buying, gross > net
    (gross, net, tradingFee) = getBuyPrice(tokenId, amount);
    // revert trades that require too low volume but still allow premints that require 0 value
    >>> totalSupply(tokenId) + amount > _marketParams.premint // @audit - premint here can be lower tha
    && (amount < MINIMUM_TRADE_SIZE || net == 0)
    revert TradeSizeOutOfRange();
    // ...
}
```
Users who only want to mint the rest of the free pre-mint from the actual p inside curve parameters will always revert because the net will be 0.

## Proof of Concept

No poc.

## Recommendation

Consider checking against the p from curve parameters instead of _marketParams.premint.
```solidity
+ (, uint256 p) = _marketParams.priceCurve.decodeParameters(_marketParams.curveParameters);
- totalSupply(tokenId) + amount > _marketParams.premint
+ totalSupply(tokenId) + amount > p
    && (amount < MINIMUM_TRADE_SIZE || net == 0)
    revert TradeSizeOutOfRange();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical inconsistency between the premint value stored in the market parameters and the premint (p) defined inside the price curve configuration. When a market is created, the contract only checks that calling getBuyPrice with the stored params.premint returns zero, allowing the stored premint to be lower than the curve’s internal p. Later, during the mint function, the code validates the requested amount against the stored _marketParams.premint instead of the curve’s actual p. The validation condition combines a supply check with a clause that reverts when the net price is zero (net == 0) or the trade size is below a minimum. If the curve’s p is greater than the stored premint, a user attempting to mint the remaining free allocation (where net price should be zero) triggers the condition, causing the transaction to revert with TradeSizeOutOfRange. This makes it impossible for users to claim the free pre‑minted tokens, resulting in a user‑facing symptom where a mint transaction fails, no tokens are received, and the user’s balance remains unchanged despite expecting a free allocation. The impact is limited to the free‑mint path: users cannot obtain the intended zero‑cost tokens, potentially affecting the distribution model and user trust, while normal paid trades continue to work. The bug occurs only when the market’s premint parameter is lower than the curve’s p and a user tries to mint an amount that would result in a zero net price. It was discovered during a manual audit that highlighted the mismatch between the parameter check at market creation and the later use of the same parameter in mint logic. The issue is subtle because the creation‑time sanity check passes, masking the later failure that only manifests under specific free‑mint conditions, making it hard to notice without targeted testing. To fix the problem, the mint function should retrieve the curve’s actual premint (p) from its decoded parameters and use that value for the supply comparison, or the stored premint should be enforced to match the curve’s p at creation, thereby aligning the validation logic with the pricing model.

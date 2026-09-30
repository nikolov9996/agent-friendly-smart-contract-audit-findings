---
id: 22664
severity: "High"
---

# Empty orders do not request from oracle and

## Description

When market.update which doesn't change user's position is called, a new (current)
global order is created, but the oracle version is not requested due to empty order.
This means that during the order settlement, it will use non-existant invalid oracle
version with price = 0. This price is then used to accumulate all the data in this
invalid Version, meaning accounting is done using price = 0, which is totally
incorrect. For instance, all funding and fees calculations multiply by oracle version's
price, thus all time periods between empty order and the next valid oracle version
will not accumulate any fees, which is funds usually lost by makers (as makers
won't receive fees/funding for the risk they take).
When market.update is called, it requests a new oracle version at the current
order's timestamp unless the order is empty:
```solidity
// request version
if (!newOrder.isEmpty()) oracle.request(IMarket(this), account);
```
The order is empty when it doesn't modify user position:
```solidity
function isEmpty(Order memory self) internal pure returns (bool) {
    return pos(self).isZero() && neg(self).isZero();
}
function pos(Order memory self) internal pure returns (Position memory) {
    return self.makerPos.add(self.longPos).add(self.shortPos);
}
function neg(Order memory self) internal pure returns (Position memory) {
    return self.makerNeg.add(self.longNeg).add(self.shortNeg);
}
```
Later, when a valid oracle version is commited, during the settlement process,
oracle version at the position is used:
```solidity
function _processOrderGlobal(
    Context memory context,
    SettlementContext memory settlementContext,
    uint256 newOrderId,
    Order memory newOrder
) private {
    // price=0
    OracleVersion memory oracleVersion = oracle.at(newOrder.timestamp);
    context.pending.global.sub(newOrder);
    // price=0 is still used everywhere
    if (!oracleVersion.valid) newOrder.invalidate();
    VersionAccumulationResult memory accumulationResult;
    (settlementContext.latestVersion, context.global, accumulationResult) =
    VersionLib.accumulate(
        // price=0 will still be used here
        settlementContext.latestVersion,
        context.global,
        context.latestPosition.global,
        newOrder,
        settlementContext.orderOracleVersion,
        context.marketParameter,
        context.riskParameter
    );
    ...
}
```
If the oracle version is invalid, the order is invalidated, but the price=0 is still used
version is always valid, thus the correct price is used to evaluate all possible
account actions, however it does affect accumulated fees and funding:
```solidity
function _accumulateLinearFee(
    Version memory next,
    AccumulationContext memory context,
    VersionAccumulationResult memory result
) private pure {
    _accumulateSubtractiveFee(
        context.riskParameter.makerFee.linear(
            invalid oracle version
        ),
        context.order.makerTotal(),
        context.order.makerReferral,
        next.makerLinearFee
    );
    ...
}
// Compute long-short funding rate
context.riskParameter.pController,
context.fromOracleVersion.timestamp,
context.toOracleVersion.timestamp,
context.fromPosition.takerSocialized().mul(context.fromOracleVersion.pri c e),
);

function _accumulateInterest(
    Version memory next,
    AccumulationContext memory context
).min(context.fromPosition.maker).mul(context.fromOracleVersion.price.abs());
...
```
As can be seen, all funding and fees accumulations multiply by oracle version's
price (which is 0), thus during these time intervals fees and funding are 0.
This will happen by itself during any period when there are no orders, because
oracle provider's settlement callback uses market.update with empty order to settle
user account, thus any non-empty order is always followed by an empty order for
the next version and price = 0 will be used to settle it until the next non-empty
order:
```solidity
function _settle(IMarket market, address account) private {
    // ...
}
```
All fees and funding are incorrectly calculated as 0 during any period when there
are no non-empty orders (which will be substantially more than 50% of the time,
more like 90% of the time). Since most fees and funding are received by makers as
a compensation for their price risk, this means makers will lose all these
under-calculated fees and will receive a lot less fees and funding than expected.

## Proof of Concept

The scenario above is demonstrated in the test, add this to
test/unit/market/Market.test.ts:
```ts
it('no fees accumulation due to invalid version with price = 0', async () => {
    function setupOracle(price: string, timestamp : number, nextTimestamp : number) {
        const oracleVersion = {
            price: parse6decimal(price),
            timestamp: timestamp,
            valid: true,
        }
        oracle.at.whenCalledWith(oracleVersion.timestamp).returns(oracleVersion)
        oracle.status.returns([oracleVersion, nextTimestamp])
        oracle.request.returns()
    }
    function setupOracleAt(price: string, valid : boolean, timestamp : number) {
        const oracleVersion = {
            price: parse6decimal(price),
            timestamp: timestamp,
            valid: valid,
        }
        oracle.at.whenCalledWith(oracleVersion.timestamp).returns(oracleVersion)
    }
    const riskParameter = { ...(await market.riskParameter()) }
    const riskParameterMakerFee = { ...riskParameter.makerFee }
    riskParameterMakerFee.linearFee = parse6decimal('0.005')
    riskParameterMakerFee.proportionalFee = parse6decimal('0.0025')
    riskParameterMakerFee.adiabaticFee = parse6decimal('0.01')
    riskParameter.makerFee = riskParameterMakerFee
    const riskParameterTakerFee = { ...riskParameter.takerFee }
    riskParameterTakerFee.linearFee = parse6decimal('0.005')
    riskParameterTakerFee.proportionalFee = parse6decimal('0.0025')
    riskParameterTakerFee.adiabaticFee = parse6decimal('0.01')
    riskParameter.takerFee = riskParameterTakerFee
    await market.connect(owner).updateRiskParameter(riskParameter)
    dsu.transferFrom.whenCalledWith(user.address, market.address, COLLATERAL.mul(1e12)).returns(true)
    dsu.transferFrom.whenCalledWith(userB.address, market.address, COLLATERAL.mul(1e12)).returns(true)
    setupOracle('100', TIMESTAMP, TIMESTAMP + 100);
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address,
        POSITION, 0, 0, COLLATERAL, false);
    await market
        .connect(userB)
        ['update(address,uint256,uint256,uint256,int256,bool)'](userB.address, 0,
        POSITION, 0, COLLATERAL, false);
    setupOracle('100', TIMESTAMP + 100, TIMESTAMP + 200);
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address,
        POSITION, 0, 0, 0, false);
    // oracle is commited at timestamp+200
    setupOracle('100', TIMESTAMP + 200, TIMESTAMP + 300);
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address,
        POSITION, 0, 0, 0, false);
    // oracle is not commited at timestamp+300
    setupOracle('100', TIMESTAMP + 200, TIMESTAMP + 400);
    setupOracleAt('0', false, TIMESTAMP + 300);
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address,
        POSITION, 0, 0, 0, false);
    // settle to see makerValue at all versions
    setupOracle('100', TIMESTAMP + 400, TIMESTAMP + 500);
    await market.settle(user.address);
    await market.settle(userB.address);
    var ver = await market.versions(TIMESTAMP + 200);
    console.log("version 200: longValue: " + ver.longValue + " makerValue: " + ver.makerValue);
    var ver = await market.versions(TIMESTAMP + 300);
    console.log("version 300: longValue: " + ver.longValue + " makerValue: " + ver.makerValue);
    var ver = await market.versions(TIMESTAMP + 400);
    console.log("version 400: longValue: " + ver.longValue + " makerValue: " + ver.makerValue);
})
```
Console log:
version 200: longValue: -318 makerValue: 285
version 300: longValue: -100000637 makerValue: 100500571
version 400: longValue: -637 makerValue: 571
Notice, that fees are accumulated between versions 200 and 300, version 300 has
huge pnl (because it's evaluated at price = 0), which then returns to normal at
version 400, but no fees are accumulated between version 300 and 400 due to
version 300 having price = 0.

## Recommendation

Keep the price from the previous valid oracle version and use it instead of oracle
version's one if oracle version's price == 0.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error that occurs when the market contract processes an empty order during a market.update call. An empty order is defined as one that does not modify the user’s position, meaning both the positive and negative position deltas are zero. Because the order is empty, the contract skips the oracle request that would normally provide a fresh price feed for the current timestamp. Consequently, when the settlement logic later retrieves the oracle version for that timestamp, it receives an oracle record whose price field is zero and whose validity flag is false. The settlement code still uses this zero price to calculate funding rates, linear fees, interest and other accounting values, even though the order is marked as invalid. As a result, all fee and funding accumulations for the time interval between the empty order and the next non‑empty order are multiplied by zero, effectively recording no fees or funding for that period. Makers, who rely on these fees as compensation for the risk they provide, lose the expected revenue, and the protocol’s accounting deviates from its business logic, showing inflated or deflated PnL values when a zero‑price version is later overwritten. The bug manifests whenever market.update is invoked without a position change – a situation that can happen frequently, potentially covering more than ninety percent of the time in a typical trading lifecycle. Users experience symptoms such as makerValue or longValue remaining unchanged, sudden large PnL spikes followed by a return to normal, and a complete lack of fee accrual despite active positions. The issue was discovered during a security audit through unit‑test simulation that forced an oracle version with price zero and observed the resulting fee calculations. It is hard to notice because the contract does not revert or emit explicit errors; the zero price silently propagates through the accounting formulas. The root cause is the conditional oracle request that assumes a non‑empty order guarantees a valid price, ignoring the possibility of a valid timestamp without a price. To fix the problem, the settlement routine should retain the last known valid oracle price and reuse it whenever the current oracle version reports a zero or invalid price, ensuring that fee and funding calculations always use a meaningful price reference. This class of bug belongs to oracle handling and accounting mis‑use, where missing price data leads to division‑by‑zero‑like effects in financial calculations, breaking the protocol’s economic guarantees.

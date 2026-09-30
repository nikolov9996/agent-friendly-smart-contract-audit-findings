---
id: 2649
severity: "High"
---

# InvariantLib uses current position for multiple times

## Description

In normal update, the InvariantLib.validate uses the currentPosition for margin check:
```solidity
if (
    !PositionLib.margined(
        updateContext.currentPositionLocal.magnitude(),
        context.latestOracleVersion,
        context.riskParameter,
        updateContext.collateralization,
        context.local.collateral.add(newGuarantee.priceAdjustment(context.latestOracleVersion.price)) // apply price override adjustment from intent if present
    )
) revert IMarket.MarketInsufficientMarginError();
```
However, during liquidation (protected = true), latestPosition is used for maintenence check:
```solidity
if (context.latestPositionLocal.maintained(
    context.latestOracleVersion,
    context.riskParameter,
    context.local.collateral
)) return false; // latest position is properly maintained
```
The latest position is position at the last commited price, while current position is expected position when price is commited for the current epoch (latest + pending). These are 2 totally different values. Usage of currentPosition in margined check means that user is allowed to withdraw collateral based on ”pending” position (which might still be invalidated). This is wrong by itself, but usage of latestPosition in liquidation maintenence check means that normal updates and liquidations are disconnected: perfectly fine normal update can easily cause unexpected immediate liquidation after the user withdraws collateral.
Incorrect usage of currentPosition in margined check in InvariantLib.validate: al-v2/packages/core/contracts/libs/InvariantLib.sol#L87-L93
Additionally, liquidation uses latestPosition in maintenence check: al-v2/packages/core/contracts/libs/InvariantLib.sol#L124-L128
Internal pre-conditions
• User reduces position and withdraws collateral, keeping healthy collateral for new (reduced) position.
External pre-conditions
None.
Attack Path
Happens by itself:
• User reduces position (e.g., from 10 to 5) and withdraws collateral, keeping enough to keep new reduced position healthy (e.g. withdrawing half of collateral).
• User account becomes immediately liquidatable and user is liquidated by any liquidator.
• Result: user is unfairly liquidated, losing liquidation and trading fees
User crafts self-liquidation to steal liquidation fees (can be profitable depending on trading fees and liquidation fee):
• Attacker opens position from account1
• Awaits settlement
• Attacker then closes full position from account1 and withdraws all collateral (allowed, since currentPosition == 0, so 0 collateral needed in margined check)
• Attacker immediately liquidates account1 from account2.
• Result: account1 is in bad debt, account2 earns liquidation fees.
If user is unfairly liquidated: easily 1%+ funds loss from liquidation. For example:
• Margin ratio is 1.2%, maintenence ratio is 1%
• Trading fee is 0.3%
• Asset price = 1000
• User has position size = 10, collateral = 200 (margin = 200 / (10*1000) = 2%)
• User reduces position size to 5 (fee = 5000*0.3% = 15), withdraws collateral = 95. Remaining collateral = 90. Margin = 95 / (5 * 1000) = 1.8%
• But the position is immediately liquidated (because maintenence for liquidation purpose = 95 / (10 * 1000) = 0.95%)
• User has position unfairly liquidated and loses fee of 15, so his loss is 15 / 90 = 17%
If liquidation bonus for liquidator is higher than trading fees from the position, then attacker can repeatedly self-liquidate until all market funds are withdrawn via liquidation fees.

## Proof of Concept

Add to test/unit/Market.test.ts in the invariant violations context:
```ts
it('reduced position with collateral withdrawal makes liquidatable position', async () => {
    const riskParameter = { ...(await market.riskParameter()) }
    const riskParameterTakerFee = { ...riskParameter.takerFee }
    riskParameterTakerFee.linearFee = parse6decimal('0.003')
    riskParameter.takerFee = riskParameterTakerFee
    riskParameter.margin = parse6decimal('0.012')
    riskParameter.maintenance = parse6decimal('0.01')
    riskParameter.minMargin = parse6decimal('5')
    riskParameter.minMaintenance = parse6decimal('5')
    await market.updateRiskParameter(riskParameter)
    const COLLATERAL_USER = parse6decimal('30')
    const POSITION_USER = parse6decimal('10')
    const POSITION2_USER = parse6decimal('5')
    const COLLATERAL2_USER = parse6decimal('15')
    dsu.transferFrom.whenCalledWith(user.address, market.address, COLLATERAL_USER.mul(1e12)).returns(true)
    dsu.transferFrom.whenCalledWith(userB.address, market.address, COLLATERAL.mul(1e12)).returns(true)
    dsu.transferFrom.whenCalledWith(userC.address, market.address, COLLATERAL_USER.mul(1e12)).returns(true)
    await market
        .connect(userB)
        ['update(address,uint256,uint256,uint256,int256,bool)'](
            userB.address,
            POSITION,
            0,
            0,
            COLLATERAL,
            false,
        )
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address, 0, POSITION_USER, 0, COLLATERAL_USER, false)
    oracle.at.whenCalledWith(ORACLE_VERSION_2.timestamp).returns([ORACLE_VERSION_2, INITIALIZED_ORACLE_RECEIPT])
    oracle.at.whenCalledWith(ORACLE_VERSION_3.timestamp).returns([ORACLE_VERSION_3, INITIALIZED_ORACLE_RECEIPT])
    oracle.at.whenCalledWith(ORACLE_VERSION_4.timestamp).returns([ORACLE_VERSION_4, INITIALIZED_ORACLE_RECEIPT])
    oracle.status.returns([ORACLE_VERSION_2, ORACLE_VERSION_3.timestamp])
    // position opened. now partially close position and withdraw collateral
    dsu.transfer.whenCalledWith(user.address, COLLATERAL2_USER.mul(1e12)).returns(true)
    await market
        .connect(user)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address, 0, POSITION2_USER, 0, -COLLATERAL2_USER, false)
    var loc = await market.locals(user.address);
    console.log("user collateral before liquidation: " + loc.collateral);
    // user becomes immediately liquidatable
    await market
        .connect(userC)
        ['update(address,uint256,uint256,uint256,int256,bool)'](user.address, 0, 0, 0, 0, true)
    oracle.status.returns([ORACLE_VERSION_3, ORACLE_VERSION_4.timestamp])
    await settle(market, user)
    await settle(market, userB)
    await settle(market, userC)
    var loc = await market.locals(user.address);
    console.log("user collateral: " + loc.collateral);
    var pos = await market.positions(user.address);
    console.log("user pos: long = " + pos.long);
})
```
Console output:
user collateral before liquidation: 11310000
user collateral: 7472950
user pos: long = 0
Demonstrates the user who reduced position from 10 to 5, is liquidated and his collateral reduces from 11.31 to 7.47 (actually, 11.31 doesn't include pending fees, so real collateral after fees is 9.31 before liquidation, 7.47 after unfair liquidation).

## Recommendation

1. Do not use currentPosition in margin check. Previously, the marin check had latestPosition + pending.maxPositive, which was correct. With the new system it might make sense to add pending.maxPositive if pending.invalidation == 1, or currentPosition if pending.invalidation == 0
2. Make sure that liquidation maintenence check matches normal update margin check, so use the same position size for the check.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from an inconsistency in how the market contract validates margin requirements during normal updates versus liquidation checks. In a normal update the library InvariantLib.validate calls a margin‑check function that uses the currentPosition – the position that includes pending changes for the current epoch – to determine whether the user’s collateral is sufficient. During a liquidation (when the protected flag is true) the same library instead uses the latestPosition – the position that was last committed before any pending changes – to perform the maintenance‑ratio check. Because currentPosition and latestPosition can differ substantially, a trader can reduce a position and withdraw collateral based on the pending (smaller) position while the liquidation logic still evaluates the larger, previously committed position. This mismatch allows a user to appear healthy to the update logic but instantly become under‑collateralised under the liquidation logic, leading to an unexpected liquidation. The attack scenario is straightforward: a user (or an attacker) reduces a long position, withdraws enough collateral to keep the reduced position marginally safe, and then either a third‑party liquidator or the attacker themselves triggers a liquidation. The liquidation check sees the old larger position, deems the account under‑maintained, and liquidates it, causing the user to lose the withdrawn collateral and any accrued trading fees. In a self‑liquidation variant the attacker can close the position completely, withdraw all collateral (the margin check passes because currentPosition becomes zero), and then immediately liquidate the now empty account, earning the liquidation bonus while the original account ends up in bad debt. The impact can be a loss of 1 % or more of the user’s funds, and if the liquidation bonus exceeds typical trading fees the attacker could repeatedly drain market funds through profit‑making self‑liquidations. The bug appears only when a position is changed and a liquidation is attempted in the same epoch; normal tests that evaluate each check in isolation may not reveal the problem, making it hard to notice. It was discovered during an audit by Sherlock through an invariant test that simulated a reduced position followed by a liquidation, exposing the discrepancy between the two checks. The issue violates the core accounting assumption that margin and maintenance checks should be based on the same position snapshot, breaking the expected relationship between collateral, position size, and safety ratios. To remediate, the margin check should be performed against the latest committed position plus any pending positive adjustments (or use the same snapshot as the liquidation check), and the liquidation maintenance check should use the identical position value as the normal update check, ensuring both paths evaluate the same collateral‑to‑position ratio.

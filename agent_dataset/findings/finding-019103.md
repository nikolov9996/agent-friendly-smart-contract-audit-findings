---
id: 19103
severity: "High"
---

# Attacker can prevent rewards from being issued to gauges for a given epoch in TapiocaOptionBroker

## Description

An attacker can prevent rewards from being issued to gauges for a given epoch

## Proof of Concept

`TapOFT.emitForWeek()` is callable by anyone. The function will only return a value > 0 the first time it’s called in any given week:

```solidity
///-- Write methods --
/// @notice Emit the TAP for the current week
/// @return the emitted amount
function emitForWeek() external notPaused returns (uint256) {
    require(_getChainId() == governanceChainIdentifier, "chain not valid");

    uint256 week = _timestampToWeek(block.timestamp);
    if (emissionForWeek[week] > 0) return 0;

    // Update DSO supply from last minted emissions
    dso_supply -= mintedInWeek[week - 1];

    // Compute unclaimed emission from last week and add it to the current week emission
    uint256 unclaimed = emissionForWeek[week - 1] - mintedInWeek[week - 1];
    uint256 emission = uint256(_computeEmission());
    emission += unclaimed;
    emissionForWeek[week] = emission;

    emit Emitted(week, emission);

    return emission;
}
```

In `TapiocaOptionBroker.newEpoch()` the return value of `emitForWeek()` is used to determine the amount of tokens to distribute to the gauges. If the return value is 0, it will assign 0 reward tokens to each gauge:

```solidity
/// @notice Start a new epoch, extract TAP from the TapOFT contract,
///         emit it to the active singularities and get the price of TAP for the epoch.
function newEpoch() external {
    require(
        block.timestamp >= lastEpochUpdate + EPOCH_DURATION,
        "tOB: too soon"
    );
    uint256[] memory singularities = tOLP.getSingularities();
    require(singularities.length > 0, "tOB: No active singularities");

    // Update epoch info
    lastEpochUpdate = block.timestamp;
    epoch++;

    // Extract TAP

    // @audit `emitForWeek` can be called by anyone. If it's called for a given
    // week, subsequent calls will return `0`. 
    // 
    // Attacker calls `emitForWeek` before it's executed through `newEpoch()`.
    // The call to `newEpoch()` will cause `emitForWeek` to return `0`.
    // That will prevent it from emitting any of the TAP to the gauges.
    // For that epoch, no rewards will be distributed to users.
    uint256 epochTAP = tapOFT.emitForWeek();
    _emitToGauges(epochTAP);

    // Get epoch TAP valuation
    (, epochTAPValuation) = tapOracle.get(tapOracleData);
    emit NewEpoch(epoch, epochTAP, epochTAPValuation);
}
```

An attacker who frontruns the call to `newEpoch()` with a call to `emitForWeek()` will prevent any rewards from being distributed for a given epoch.

The reward tokens aren’t lost. TapOFT will roll the missed epoch’s rewards into the next one. Meaning, the gauge rewards will be delayed. The length depends on the number of times the attacker is able to frontrun the call to `newEpoch()`.

But, it will cause the distribution to be screwed. If Alice is eligible for gauge rewards until epoch x + 1 (her lock runs out), and the attacker manages to keep the attack running until x + 2, she won’t be able to claim her reward tokens. They will be distributed in epoch x + 3 to all the users who have an active lock at that time.

Here’s a PoC:

```solidity
// tOB.test.ts
it.only("should fail to emit rewards to gauges if attacker frontruns", async () => {
    const {
        tOB,
        tapOFT,
        tOLP,
        sglTokenMock,
        sglTokenMockAsset,
        tapOracleMock,
        sglTokenMock2,
        sglTokenMock2Asset,
    } = await loadFixture(setupFixture);

    // Setup tOB
    await tOB.oTAPBrokerClaim();
    await tapOFT.setMinter(tOB.address);

    // No singularities
    await expect(tOB.newEpoch()).to.be.revertedWith(
        'tOB: No active singularities',
    );

    // Register sgl
    const tapPrice = BN(1e18).mul(2);
    await tapOracleMock.set(tapPrice);
    await tOLP.registerSingularity(
        sglTokenMock.address,
        sglTokenMockAsset,
        0,
    );

    await tapOFT.emitForWeek();

    await tOB.newEpoch();

    const emittedTAP = await tapOFT.getCurrentWeekEmission();

    expect(await tOB.singularityGauges(1, sglTokenMockAsset)).to.be.equal(
        emittedTAP,
    );
})
```

Test output:

```
  TapiocaOptionBroker
    1) should fail to emit rewards to gauges if attacker frontruns

  0 passing (1s)
  1 failing

  1) TapiocaOptionBroker
       should fail to emit rewards to gauges if attacker frontruns:

      AssertionError: expected 0 to equal 469157964000000000000000. The numerical values of the given "ethers.BigNumber" and "ethers.BigNumber" inputs were compared, and they differed.
      + expected - actual

      -0
      +469157964000000000000000

      at Context.<anonymous> (test/oTAP/tOB.test.ts:606:73)
      at processTicksAndRejections (node:internal/process/task_queues:96:5)
      at runNextTicks (node:internal/process/task_queues:65:3)
      at listOnTimeout (node:internal/timers:528:9)
      at processTimers (node:internal/timers:502:7)
```

## Recommendation

`emitForWeek()` should return the current week’s emitted amount if it was already called:

```solidity
function emitForWeek() external notPaused returns (uint256) {
    require(_getChainId() == governanceChainIdentifier, "chain not valid");

    uint256 week = _timestampToWeek(block.timestamp);
    if (emissionForWeek[week] > 0) return emissionForWeek[week];
    // ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reward‑emission race condition in the TapiocaOptionBroker system. The contract TapiocaOptionBroker relies on the external TapOFT contract to emit a weekly amount of TAP tokens through the function emitForWeek(). This function is public and can be called by any address. Its logic records the emission for the current week the first time it is invoked and returns zero on any subsequent call within the same week. In the normal flow, newEpoch() calls emitForWeek() exactly once per epoch, uses the returned amount to distribute rewards to gauge contracts, and then records the epoch information. Because emitForWeek() is not restricted, an attacker can front‑run the newEpoch() transaction by calling emitForWeek() earlier in the same block or shortly before newEpoch() is executed. When newEpoch() later invokes emitForWeek(), the function sees that the week’s emission has already been recorded and returns zero. Consequently, the variable epochTAP receives a value of zero and the subsequent call to _emitToGauges distributes no reward tokens for that epoch. The root cause is the lack of access control on emitForWeek() and the assumption that only the protocol will call it once per week. The exploit can be carried out by any external actor who can submit a transaction before the protocol’s scheduled newEpoch() call, which is feasible in a public blockchain where transaction ordering is not guaranteed. The impact is that gauge participants who are eligible for rewards in the affected epoch receive nothing, even though the protocol’s accounting still shows that rewards exist. From the user’s perspective the UI will display a zero balance or no reward claimable for that week, contradicting the expectation that they should receive a proportional share of TAP. The funds are not burned; the unclaimed emission is rolled into the next week’s emission, causing a delay in reward distribution. Users whose lock expires before the delayed epoch may miss their entitlement entirely, as the reward will be allocated to later participants. This issue was discovered during a security audit when a test case demonstrated that calling emitForWeek() before newEpoch() caused the reward amount to be zero. The bug is subtle because the contract does not revert or emit an error; it simply results in a missing reward, which can be mistaken for a normal zero‑reward epoch. To remediate the problem the emitForWeek() function should be restricted to the protocol (e.g., internal or onlyOwner) or should return the already stored emission amount instead of zero when called again, ensuring that newEpoch() always receives the correct weekly emission regardless of external calls. This class of bug falls under uncontrolled external calls leading to state‑dependent logic errors, often referred to as a front‑running or race‑condition vulnerability in reward‑distribution mechanisms.

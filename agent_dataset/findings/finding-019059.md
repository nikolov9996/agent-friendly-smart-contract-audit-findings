---
id: 19059
severity: "High"
---

# `exitPosition` in `TapiocaOptionBroker` may incorrectly inflate position weights

## Description

```solidity
Users who `participate()` and place stakes with large magnitudes may have their weight removed prematurely from `pool.cumulative`, hence causing the weight logic of participation to be wrong. `pool.cumulative` will have an incomplete image of the actual pool hence allowing future users to have divergent power when they should not. In particular, this occurs during the `exitPosition()` function.
```

## Proof of Concept

```solidity
This vulnerability stems from `exitPosition()` using the current `pool.AverageMagnitude` instead of the respective magnitudes of the user’s weights to update `pool.cumulative` on line 316. Hence, when users call `exitPosition()`, the amount that `pool.cumulative` is updated but may not be representative of the weight of the user’s input.

Imagine if we have three users, Alice, Bob, and Charlie who all decide to call `participate()`. Alice calls `participate()` with a smaller amount and a smaller time, hence having a weight of 10. Bob calls `participate()` with a larger amount and a larger time, hence having a weight of 50. Charlie calls `participate()` with a weight of 20.

  * Alice calls `participate()` first at time 0 with the aforementioned amount and time. The `pool.cumulative` is now 10 and the `pool.AverageMagnitude` is 10 as well. Alice’s position will expire at time 10.
  * Bob calls `participate()` at time 5. The `pool.cumulative` is now 10 + 50 = 60 and the `pool.AverageMagnitude` is 50.
  * Alice calls `exitPosition()` at time 10. `pool.cumulative` is 60, but `pool.AverageMagnitude` is still 50. Hence, `pool.cumulative` will be decreased by 50, even though the weight of Alice’s input is 10.
  * Charlie calls `participate` with weight 20. Charlie will have divergent power in the pool with both Bob and Charlie, since 20 > `pool.cumulative` (10).

If Alice does not participate at all, Charlie will not have divergent power in a pool with Bob and Charlie, since the `pool.cumulative` = Bob’s weight = 50 > Charlie’s weight (20).

We have provided a test to demonstrate the `pool.cumulative` inflation. Copy the following code into`tap-token-audit/test/oTAP/tOB.test.ts` as one of the tests.
    
    it('POC', async () => {
            const {
                signer,
                tOLP,
                tOB,
                tapOFT,
                sglTokenMock,
                sglTokenMockAsset,
                yieldBox,
                oTAP,
            } = await loadFixture(setupFixture);
    
            // Setup tOB
            await tOB.oTAPBrokerClaim();
            await tapOFT.setMinter(tOB.address);
    
            // Setup - register a singularity, mint and deposit in YB, lock in tOLP
            const amount = 3e10;
            const lockDurationA = 10;
            const lockDurationB = 100;
            await tOLP.registerSingularity(
                sglTokenMock.address,
                sglTokenMockAsset,
                0,
            );
    
            await sglTokenMock.freeMint(amount);
            await sglTokenMock.approve(yieldBox.address, amount);
            await yieldBox.depositAsset(
                sglTokenMockAsset,
                signer.address,
                signer.address,
                amount,
                0,
            );
    
            const ybAmount = await yieldBox.toAmount(
                sglTokenMockAsset,
                await yieldBox.balanceOf(signer.address, sglTokenMockAsset),
                false,
            );
            await yieldBox.setApprovalForAll(tOLP.address, true);
            //A (short less impact)
            console.log(ybAmount);
            await tOLP.lock(
                signer.address,
                sglTokenMock.address,
                lockDurationA,
                ybAmount.div(100),
            );
            //B (long, big impact)
            await tOLP.lock(
                signer.address,
                sglTokenMock.address,
                lockDurationB,
                ybAmount.div(2),
            );
            const tokenID = await tOLP.tokenCounter();
            const snapshot = await takeSnapshot();
            console.log("A Duration: ", lockDurationA, " B Duration: ", lockDurationB);
            // Just A Participate
            console.log("Just A participation");
            await tOLP.approve(tOB.address, tokenID.sub(1));
            await tOB.participate(tokenID.sub(1));
            const participationA = await tOB.participants(tokenID.sub(1));
            const oTAPTknID = await oTAP.mintedOTAP();
            await time.increase(lockDurationA);
            const prevPoolState = await tOB.twAML(sglTokenMockAsset);
            console.log("[B4] Just A Cumulative: ", await prevPoolState.cumulative);
            console.log("[B4] Just A Average: ", participationA.averageMagnitude);
            await oTAP.approve(tOB.address, oTAPTknID);
            await tOB.exitPosition(oTAPTknID);
            console.log("Exit A position");
            const newPoolState = await tOB.twAML(sglTokenMockAsset);
            console.log("[A4] Just A Cumulative: ", await newPoolState.cumulative);
            console.log("[A4] Just A Average: ", await participationA.averageMagnitude);
    
            //Both Participations
            console.log();
            console.log("Run both participation---");
            const ctime1 = new Date();
            console.log("Time: ", ctime1);
            //A and B Participate
            await snapshot.restore();
            //Before everything
            const initPoolState = await tOB.twAML(sglTokenMockAsset);
            console.log("[IN] Initial Cumulative: ", await initPoolState.cumulative);
            //First participate A
            await tOLP.approve(tOB.address, tokenID.sub(1));
            await tOB.participate(tokenID.sub(1));
            const xparticipationA = await tOB.participants(tokenID.sub(1));
            const ATknID = await oTAP.mintedOTAP();
            console.log("Participate A (smaller weight)");
            console.log("[ID] A Token ID: ", ATknID);
            const xprevPoolState = await tOB.twAML(sglTokenMockAsset);
            console.log("[B4] Both A Cumulative: ", await xprevPoolState.cumulative);
            console.log("[B4] Both A Average: ", await xparticipationA.averageMagnitude);
            console.log();
    
            //Time skip to half A's duration
            await time.increase(5);
            const ctime2 = new Date();
            console.log("Participate B (larger weight), Time(+5): ", ctime2);
    
            //Participate B
            await tOLP.approve(tOB.address, tokenID);
            await tOB.participate(tokenID);
            const xparticipationB = await tOB.participants(tokenID);
            const BTknID = await oTAP.mintedOTAP();
            console.log("[ID] B Token ID: ", ATknID);
            const xbothPoolState = await tOB.twAML(sglTokenMockAsset);
            console.log("[B4] Both AB Cumulative: ", await xbothPoolState.cumulative);
            console.log("[B4] Both B Average: ", await xparticipationB.averageMagnitude);
            
            //Time skip end A
            await time.increase(6);
            await oTAP.approve(tOB.address, ATknID);
            await tOB.exitPosition(ATknID);
            const exitAPoolState = await tOB.twAML(sglTokenMockAsset);
            const ctime3 = new Date();
            console.log();
            console.log("Exit A (Dispraportionate Weight, Time(+6 Expire A): ", ctime3);
            console.log("[!X!] Just B Cumulative: ", await exitAPoolState.cumulative);
            console.log("[A4] Just B Average: ", xparticipationB.averageMagnitude);
    
            //TIme skip end B
            await time.increase(lockDurationB);
            await oTAP.approve(tOB.address, BTknID);
            await tOB.exitPosition(BTknID);
            const exitBPoolState = await tOB.twAML(sglTokenMockAsset);
            const ctime4 = new Date();
            console.log("Exit B, Time(+100 Expire B): ", ctime4);
            console.log("[A4] END Cumulative: ", await exitBPoolState.cumulative);
    
        });
```

## Recommendation

```solidity
There may be a need to store weights at the time of adding a weight instead of subtracting the last computed weight in `exitPosition()`. For example, when Alice calls `participate()`, the weight at that time is stored and removed when `exitPosition()` is called.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the exitPosition function of the TapiocaOptionBroker contract, where the routine that updates the pool's cumulative weight mistakenly uses the pool's current average magnitude instead of the specific weight contributed by the exiting participant. As a result, when a user who entered the pool with a relatively small weight exits, the contract subtracts a much larger value – the average magnitude that reflects later, larger participants – from the cumulative total. This premature removal inflates the remaining cumulative weight, causing subsequent participants to appear to have disproportionate influence or power in the pool. The bug is triggered when a participant calls exitPosition after other participants with higher magnitudes have already joined, because the average magnitude has been updated to reflect those later participants. In practice, a user such as Alice who entered with a weight of 10 and later exits while Bob has already contributed a weight of 50 will cause the pool.cumulative to be reduced by 50 instead of 10. Consequently, a later participant like Charlie, who only contributed a weight of 20, will find the pool.cumulative lower than expected, granting him more relative voting or reward power than the protocol's accounting logic intends. The impact includes distorted reward distribution, potential over‑allocation of voting rights, and a breach of the economic assumptions that the pool’s weight reflects the true sum of active positions. Users experience symptoms such as their expected share of rewards being reduced, their voting power appearing higher than justified, or the pool showing an inconsistent cumulative value after exits. The issue was uncovered during a Code4rena audit through systematic testing that revealed the cumulative inflation when exitPosition was called under varying participation scenarios. It is hard to notice because the cumulative variable still holds a numeric value that seems plausible, while the underlying weight composition is silently corrupted. The proper remediation is to record each participant’s exact weight at the time of participation and to subtract that stored weight when the participant exits, rather than relying on the mutable average magnitude. This class of bug falls under incorrect state update due to misuse of aggregate metrics, a common pattern where global averages are applied to individual removals, leading to accounting mismatches and unintended privilege escalation within decentralized finance protocols.

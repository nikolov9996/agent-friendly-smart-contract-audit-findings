---
id: 21750
severity: "High"
---

# Miscalculation in `_farmPlots` function could lead to a user unable to unstake all NFTs

## Description

The function `_farmPlots()` is used to calculate rewards farming rewards. This function is used in different scenarios, including like a modifier in the function `unstakeMunchable()` function when a user unstakes their NFT. Let’s have a look at how `finalBonus` is calculated in the function:

```solidity
finalBonus =
    int16(
        REALM_BONUSES[
            (uint256(immutableAttributes.realm) * 5) +
                uint256(landlordMetadata.snuggeryRealm)
        ]
    ) +
    int16(
        int8(RARITY_BONUSES[uint256(immutableAttributes.rarity)])
    );
```

The `finalBonus` consists of bonus from the realm (`REALM_BONUSES`), as well as a rarity bonus (`RARITY_BONUSES`).

`REALM_BONUSES` can be either `-10`, `-5`, `0`, `5` or `10`, and `RARITY_BONUSES` can be either `0`, `10`, `20`, `30` or `50`.

`finalBonus` is meant to incentivize staking Munchables in a plot in a suitable realm. It can either be a positive bonus or reduction in the amount of `schnibblesTotal`. An example of a negative scenario is when `REALM_BONUSES` is `-10` and `RARITY_BONUSES` is `0`.

Let’s look at the calculation of `schnibblesTotal`:

```solidity
schnibblesTotal =
    (timestamp - _toiler.lastToilDate) *
    BASE_SCHNIBBLE_RATE;
schnibblesTotal = uint256(
    (int256(schnibblesTotal) +
        (int256(schnibblesTotal) * finalBonus)) / 100
);
```

`schnibblesTotal` is typed as `uint256`; therefore, it is meant as always positive. The current calculation, however, will result in a negative value of `schnibblesTotal`, when `finalBonus < 0`, the conversion to uint256 will cause the value to evaluate to something near `type(uint256).max`. In that case the next calculation of `schnibblesLandlord` will revert due to overflow:

```solidity
schnibblesLandlord =
    (schnibblesTotal * _toiler.latestTaxRate) /
    1e18;
```

This is due to the fact that `_toiler.latestTaxRate > 1e16`.

Since `unstakeMunchable()` has a modifier `forceFarmPlots()`, the unstaking will be blocked if `_farmPlots()` reverts.

## Proof of Concept

Alice has a Common or Primordial Munchable NFT from Everfrost.  
Bob has land (plots) in Drench.  
Alice stakes her NFT in Bob’s plot.  
After some time Alice unstakes her NFT.  
Since in the calculation of schnibblesTotal is used a negative `finalBonus`, the transaction will revert.  
Alice’s Munchable NFT and any other staked beforehand are blocked.

Add the following lines of code in `tests/managers/LandManager/unstakeMunchable.test.ts`:

```
.
.
.
await registerPlayer({
   account: alice,
+  realm: 1,
   testContracts,
});
await registerPlayer({
   account: bob,
   testContracts,
});
await registerPlayer({
   account: jirard,
   testContracts,
});
.
.
.
await mockNFTOverlord.write.addReveal([alice, 100], { account: alice });
   await mockNFTOverlord.write.addReveal([bob, 100], { account: bob });
   await mockNFTOverlord.write.addReveal([bob, 100], { account: bob });
   await mockNFTOverlord.write.startReveal([bob], { account: bob }); // 1
-  await mockNFTOverlord.write.reveal([bob, 4, 12], { account: bob }); // 1
+  await mockNFTOverlord.write.reveal([bob, 1, 0], { account: bob }); // 1
   await mockNFTOverlord.write.startReveal([bob], { account: bob }); // 2
   await mockNFTOverlord.write.reveal([bob, 0, 13], { account: bob }); // 2
   await mockNFTOverlord.write.startReveal([bob], { account: bob }); // 3
```

When we run the command `pnpm test:typescript` the logs from the tests show that the `successful path` test reverts.

## Recommendation

`finalBonus` is meant as a percentage change in the Schnibbles earned by a Munchable. Change the calculation of `schnibblesTotal` in `_farmPlots()` to reflect that by removing the brackets:

```solidity
schnibblesTotal =
    (timestamp - _toiler.lastToilDate) *
    BASE_SCHNIBBLE_RATE;
schnibblesTotal = uint256(
    int256(schnibblesTotal) + 
       (int256(schnibblesTotal) * finalBonus) / 100
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a miscalculation in the internal reward‑distribution routine called _farmPlots, which is invoked as a modifier during the unstakeMunchable function. The routine computes a signed percentage called finalBonus by adding a realm‑specific bonus (which can be –10, –5, 0, 5 or 10) to a rarity bonus (0, 10, 20, 30 or 50). When the combined finalBonus is negative, the subsequent calculation of schnibblesTotal first multiplies the base reward by the signed finalBonus, adds the product to the base amount, and only then casts the result to uint256 inside parentheses. Because the intermediate expression can become negative, the cast to uint256 wraps the value to a very large number close to type(uint256).max. This inflated schnibblesTotal is then multiplied by the landlord’s tax rate, which is greater than 1e16, causing an arithmetic overflow and a revert. The revert happens inside the forceFarmPlots modifier, so the outer unstakeMunchable call fails and the user’s NFT remains locked in the plot. The bug is triggered only when a user stakes an NFT in a plot where the realm bonus is negative and the rarity bonus is low enough that finalBonus < 0, for example a common or primordial NFT placed in a realm with a –10 bonus. The impact is that the affected user cannot withdraw the NFT and any accrued rewards, effectively freezing assets. The issue was discovered during a formal audit when a test case that used a negative finalBonus caused the unstake transaction to revert. It is hard to notice because the reward formula looks syntactically correct and the overflow only appears for specific bonus combinations; the unsigned cast masks the sign error until the overflow check triggers. The proper fix is to treat the percentage as a signed adjustment applied before the division, i.e. compute schnibblesTotal as int256(base) + (int256(base) * finalBonus) / 100 and only then cast the final result to uint256. This eliminates the negative‑to‑unsigned conversion and prevents the overflow, restoring the ability for users to unstake their NFTs and receive correct rewards. The bug belongs to the class of signed‑to‑unsigned conversion errors that lead to underflow/overflow and transaction reverts, breaking business logic that assumes rewards are always non‑negative and that unstaking must always succeed.

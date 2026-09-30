---
id: 7615
severity: "High"
---

# totalXP is wrongly calculated for existing users

## Description

In src/staking/DyadXPv2.sol, the contract must be initialized through the initialize function, and the totalXP of each user is also calculated here:
```solidity
function initialize(address owner) public reinitializer(2) {
    __UUPSUpgradeable_init();
    __Ownable_init(msg.sender);
    uint256 dnftSupply = DNFT.totalSupply();
    for (uint256 i = 0; i < dnftSupply; ++i) {
        noteData[i] = NoteXPData({
            lastAction: uint40(block.timestamp),
            keroseneDeposited: uint96(KEROSENE_VAULT.id2asset(i)),
            lastXP: noteData[i].lastXP,
            totalXP: noteData[i].lastXP,
            dyadMinted: DYAD.mintedDyad(i)
        });
    }
}
```
However, the totalXP doesn't consider the last accrued bonus, as it is only the lastXP rather than the actual total (including the bonus) during the upgrade. This is because the elapsed time between the upgrade and their last action is very likely to not be zero:
```solidity
function _computeXP(NoteXPData memory lastUpdate) internal view returns (uint256) {
    uint256 elapsed = block.timestamp - lastUpdate.lastAction;
    uint256 deposited = lastUpdate.keroseneDeposited;
    uint256 dyadMinted = lastUpdate.dyadMinted;
    uint256 totalXP = lastUpdate.totalXP;
    uint256 accrualRateModifier = totalXP > 0 ? 1e18 / totalXP.log10() : 1e18;
    uint256 adjustedAccrualRate = accrualRateModifier * 1e7;
    // bonus = deposited + deposited * (dyadMinted /
    // (dyadMinted + deposited))
    uint256 bonus = deposited;
    if (dyadMinted + deposited != 0) {
        bonus += deposited.mulWadDown(dyadMinted.divWadDown(dyadMinted + deposited));
    }
    return uint256(lastUpdate.lastXP + (elapsed * adjustedAccrualRate * bonus) / 1e18);
}
```
A numerical example:
lastXP: 1e18
_computeXP:
elapsed: 10_000
deposited: 1e18
dyadMinted: 0
totalXP: 0
accrualRateModifier: 1e18
adjustedAccrualRate: 1e18 * 1e7 = 1e25
bonus: 1e18
0 + 1e18 != 0
bonus = 1e18 + (1e18 * (0 / (0 + 1e18)) = 1e18
1e18 + (10_000 * 1e25 * bonus) / 1e18 = 1e18 + 10_000 * 1e25
In this example, the user will have a totalXP = 1e18 with the current code, but they should have totalXP = 1e18 + 1e29 instead. This will affect the accrualRateModifier the next time the function is called (for example, to calculate rewards of a Uniswap position), as the totalXP will be lower than intended.

## Proof of Concept

No poc.

## Recommendation

Consider applying the following fix:
```solidity
function initialize(address owner) public reinitializer(2) {
    __UUPSUpgradeable_init();
    __Ownable_init(msg.sender);
    uint256 dnftSupply = DNFT.totalSupply();
    for (uint256 i = 0; i < dnftSupply; ++i) {
        uint256 totalXP = _computeXP(noteData[i]);
        noteData[i] = NoteXPData({
            lastAction: uint40(block.timestamp),
            keroseneDeposited: uint96(KEROSENE_VAULT.id2asset(i)),
            lastXP: noteData[i].lastXP,
            totalXP: totalXP,
            dyadMinted: DYAD.mintedDyad(i)
        });
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect calculation of the totalXP value for existing users that is performed during the contract upgrade initialization. The initialize function iterates over all DNFT tokens and populates each NoteXPData struct, but it assigns totalXP the value of lastXP without applying the _computeXP formula that accounts for the elapsed time and the bonus derived from deposited kerosene and minted DYAD. Because the time between a user’s last action and the upgrade is typically non‑zero, the accrued bonus is omitted, causing totalXP to be lower than it should be. An attacker or any user can exploit this by triggering the upgrade (or relying on the upgrade that already occurred) and then invoking functions that use totalXP to compute the accrualRateModifier and subsequent reward amounts. Since accrualRateModifier is inversely proportional to the logarithm of totalXP, a smaller totalXP yields a larger modifier, which inflates the adjusted accrual rate and results in higher XP or reward accrual than intended. From the user’s perspective the UI may show the same XP balance after the upgrade or a sudden, unexpected increase in rewards later, contradicting the expectation that XP grows proportionally with time. The bug affects all existing DNFT holders and any protocol component that relies on totalXP for accounting, such as Uniswap position reward calculations. It was discovered during a security audit when the reviewer compared the initialize logic with the _computeXP implementation and noticed that the bonus term was never added. The issue is subtle because the contract still records a non‑zero lastXP and the UI may not display the internal totalXP field directly, making the discrepancy easy to miss. The proper fix is to recompute totalXP for each user during initialization by calling the same _computeXP routine that is used in normal operation, thereby including the elapsed time and bonus in the stored value. This class of bug belongs to the broader category of state‑migration miscalculations where upgrade code fails to preserve derived state, leading to accounting errors and potential economic manipulation.

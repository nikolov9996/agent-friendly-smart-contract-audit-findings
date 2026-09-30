---
id: 23388
severity: "High"
---

# Historical token issuances become subject to new lock-up requirements when users change residency

## Description

The `checkHoldUp` function and `getComplianceTransferableTokens` function contain a flaw in how lock periods are applied to token issuances. The system incorrectly applies a single, current lock period to all historical issuances instead of using the lock period that was applicable when each token was originally issued.

The vulnerability stems from two key issues:
1. Lock periods are calculated at transfer time based on the investor's current country, not their country at issuance time (this is in `checkHoldUp`):

```solidity
function checkHoldUp(
    address[] memory _services,
    address _from,
    uint256 _value,
    bool _isUSLockPeriod, // ← Determined at TRANSFER time
    bool _isPlatformWalletFrom
) internal view returns (bool) {
    uint256 lockPeriod;
    if (_isUSLockPeriod) {
        lockPeriod = getUSLockPeriod(); // ← Current US lock period
    } else {
        lockPeriod = getNonUSLockPeriod(); // ← Current Non-US lock period
    }
    // ← Applies same lock period to ALL issuances!
    return complianceService.getComplianceTransferableTokens(_from, block.timestamp,
        uint64(lockPeriod)) < _value;
}
```

2. The same lock period is applied to all historical issuances for an investor, regardless of when those tokens were issued or what the applicable regulations were at that time (this is in `getComplianceTransferableTokens`):

```solidity
function getComplianceTransferableTokens(
    address _who,
    uint256 _time,
    uint64 _lockTime
) public view override returns (uint256) {
    ...
    for (uint256 i = 0; i < investorIssuancesCount; i++) {
        uint256 issuanceTimestamp = issuancesTimestamps[investor][i];
        // Uses same _lockTime for ALL issuances <-------------
        if (uint256(_lockTime) > _time || issuanceTimestamp > (_time - uint256(_lockTime))) {
            uint256 tokens =
                getRebasingProvider().convertSharesToTokens(issuancesValues[investor][i]);
            totalLockedTokens = totalLockedTokens + tokens;
        }
    }
    //there may be more locked tokens than actual tokens, so the minimum between the two
    uint256 transferable = balanceOfInvestor - Math.min(totalLockedTokens, balanceOfInvestor);
    return transferable;
}
```

Impact: * Investors may be unable to transfer tokens that should legally be unlocked (Temporally freeze of funds), causing liquidity issues.  
* Incorrect application of lock periods can lead to violations of securities regulations that require specific lock‑up periods based on investor status at issuance time.

## Proof of Concept

Consider the following real‑world scenario:

1. January 1 2024: Alice is a German investor (Non‑US, 6‑month lock period)  
2. June 1 2024: Alice relocates to USA and updates her investor profile (US, 12‑month lock period)  
3. December 1 2024: Alice attempts to transfer tokens  

Issuance history of Alice:  
- Issuance 1: January 1 2024 – 1,000 tokens (issued when Alice was German)  
- Issuance 2: March 1 2024 – 500 tokens (issued when Alice was German)  
- Issuance 3: August 1 2024 – 200 tokens (issued when Alice was US resident)  

**How it should be (correct behavior) on December 1 2024:**  
- Issuance 1: Jan 1 + 6 months = July 1 2024 → UNLOCKED  
- Issuance 2: Mar 1 + 6 months = Sep 1 2024 → UNLOCKED  
- Issuance 3: Aug 1 + 12 months = Aug 1 2025 → LOCKED  
Total transferable: 1,500 tokens; Total locked: 200 tokens  

**How it is (current flawed behavior) on December 1 2024:**  
- Issuance 1: Jan 1 + 12 months = Jan 1 2025 → LOCKED  
- Issuance 2: Mar 1 + 12 months = Mar 1 2025 → LOCKED  
- Issuance 3: Aug 1 + 12 months = Aug 1 2025 → LOCKED  
Result: All tokens are incorrectly locked.

## Recommendation

Consider storing Lock Periods at Issuance Time:

```solidity
// Add new mapping to ComplianceServiceDataStore.sol
mapping(string => mapping(uint256 => uint256)) issuanceLockPeriods;

function createIssuanceInformation(
    string memory _investor,
    uint256 _shares,
    uint256 _issuanceTime
) internal returns (bool) {
    ...
    issuancesValues[_investor][issuancesCount] = _shares;
    issuancesTimestamps[_investor][issuancesCount] = _issuanceTime;
    + issuanceLockPeriods[_investor][issuancesCount] = lockPeriod; // <----------Store lock period
    issuancesCounters[_investor] = issuancesCount + 1;
    return true;
}
```

Then adjust `getComplianceTransferableTokens` to use the stored lock period:

```solidity
function getComplianceTransferableTokens(
    address _who,
    uint256 _time,
    uint64 _lockTime // This parameter can be removed
) public view override returns (uint256) {
    ...
    for (uint256 i = 0; i < investorIssuancesCount; i++) {
        uint256 issuanceTimestamp = issuancesTimestamps[investor][i];
        + uint256 applicableLockPeriod = issuanceLockPeriods[investor][i]; // Use stored lock period
        - if (uint256(_lockTime) > _time || issuanceTimestamp > (_time - uint256(_lockTime))) {
        + if (_time < issuanceTimestamp + applicableLockPeriod) {
            uint256 tokens = getRebasingProvider().convertSharesToTokens(issuancesValues[investor][i]);
            totalLockedTokens = totalLockedTokens + tokens;
        }
    }
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a temporal lock‑up misapplication that causes all historical token issuances to be subject to the lock period associated with the investor's current residency rather than the period that was in effect when each issuance was created. The root cause lies in two functions: checkHoldUp determines a lock period at transfer time by inspecting a flag that reflects the investor's present country and then selects either the US or non‑US lock duration; this single duration is subsequently supplied to getComplianceTransferableTokens, which iterates over every issuance but uses the same lock time for each entry. Consequently, when an investor changes residency after receiving tokens, the contract retroactively applies the new, often longer, lock period to earlier issuances that should have already unlocked. Exploitation occurs during a normal transfer call: the compliance service calculates total locked tokens by adding the value of every issuance whose timestamp falls within the current lock window, which, due to the bug, includes tokens that are legally free. The impact is that users see a zero or reduced transferable balance, experience failed transfers, and may be unable to move funds that should be liquid, creating liquidity freezes and potentially violating securities regulations that mandate lock‑up periods based on the investor’s status at issuance. This condition manifests whenever an investor updates their residency profile after having received tokens, a scenario common in cross‑border investment platforms. The issue was discovered during a security audit that examined the compliance logic and identified that the lock period parameter is derived from current state rather than persisted issuance data. It can be hard to notice because the UI simply reports a locked balance without exposing per‑issuance lock details, leading users to assume a contract‑wide lock rather than a bug. The appropriate remediation is to store the applicable lock period at the moment each issuance is recorded and to reference that stored value when evaluating lock status, thereby ensuring that each token batch is unlocked according to the regulatory regime that applied at its creation. This class of bug falls under improper temporal state handling and lock‑up period misapplication, where business logic assumes a static rule but the implementation dynamically rewrites historical constraints, breaking the expectation that "tokens issued under a six‑month lock become transferable after six months" and instead enforcing "all tokens follow the current lock rule".

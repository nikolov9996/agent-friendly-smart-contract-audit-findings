---
id: 1178
severity: "High"
---

# ts.tokens sometimes calculated incorrectly

## Description

Suppose someone stakes some tokens and then withdraws all of his tokens (he can still withdraw). This will result in ts.tokens being 0.

Now after some time he stakes some tokens again. At the second stake `updateStream()` is called and the following if condition is false because `ts.tokens==0`:

```solidity
if (acctTimeDelta > 0 && ts.tokens > 0) {
```

Thus `ts.lastUpdate` is not updated and stays at the value from the first withdraw. Now he does a second withdraw. `updateStream()` is called and calculates the updated value of `ts.tokens`. However it uses `ts.lastUpdate`, which is the time from the first withdraw and not from the second stake. So the value of `ts.tokens` is calculated incorrectly. Thus more tokens can be withdrawn than you are supposed to be able to withdraw.

## Proof of Concept

```solidity
function stake(uint112 amount) public lock updateStream(msg.sender) {
    ...
    uint112 trueDepositAmt = uint112(newBal - prevBal);
    ...
    ts.tokens += trueDepositAmt;
}

function withdraw(uint112 amount) public lock updateStream(msg.sender) {
    ...
    ts.tokens -= amount;
}

function updateStreamInternal(address who) internal {
    ...
    uint32 acctTimeDelta = uint32(block.timestamp) - ts.lastUpdate;
    if (acctTimeDelta > 0 && ts.tokens > 0) {
        // some time has passed since this user last interacted
        // update ts not yet streamed
        ts.tokens -= uint112(acctTimeDelta * ts.tokens / (endStream - ts.lastUpdate));
        ts.lastUpdate = uint32(block.timestamp);
    }
}
```

## Recommendation

Change the code in updateStream() to:

```solidity
if (acctTimeDelta > 0) {
    // some time has passed since this user last interacted
    // update ts not yet streamed
    if (ts.tokens > 0)
        ts.tokens -= uint112(acctTimeDelta * ts.tokens / (endStream - ts.lastUpdate));
    ts.lastUpdate = uint32(block.timestamp);  // always update ts.lastUpdate (if time has elapsed)
}
```

Note: the next if statement with unstreamed and lastUpdate can be changed in a similar way to save some gas

> Nice catch :)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a time‑based accounting error in the streaming contract that incorrectly updates the user’s last interaction timestamp when the token balance temporarily reaches zero. The root cause is a conditional guard in the updateStreamInternal function that only updates ts.lastUpdate if both a positive time delta and a positive token balance (ts.tokens > 0) are present. When a user withdraws all tokens, ts.tokens becomes zero and the guard blocks the timestamp update. If the same user stakes additional tokens later, the function again evaluates the guard; because ts.tokens is now greater than zero but the previous guard prevented ts.lastUpdate from being refreshed, the timestamp remains stale from the earlier withdrawal. Subsequent withdrawals use this stale ts.lastUpdate to compute the streamed amount, applying a longer elapsed interval than actually occurred. The calculation therefore deducts fewer tokens than should have been streamed, allowing the user to withdraw more than the entitled amount. This can be exploited by an attacker who fully withdraws, waits, restakes a small amount, and then immediately withdraws again, receiving extra tokens that were never earned. The impact is a violation of the protocol’s token accounting guarantees, leading to loss of value for other participants and potential depletion of the contract’s token pool. The condition occurs whenever a user’s balance hits zero and later becomes non‑zero without an intervening update of the last timestamp, a scenario that is common in staking/withdrawal cycles. All users of the contract, as well as the protocol’s treasury, are affected because the bug can be repeatedly triggered by any participant. The issue was discovered during a manual audit that exercised the stake‑withdraw‑stake‑withdraw flow and observed that the token balance after the second withdrawal exceeded the expected amount. It is hard to notice because the contract’s normal operation with non‑zero balances works correctly, and the faulty path only activates after a full withdrawal, which may not be covered by standard unit tests. To remediate, the timestamp should be refreshed whenever any time has elapsed, regardless of the current token balance, and the token deduction logic should be guarded separately. In practice this means moving the ts.lastUpdate assignment outside the ts.tokens > 0 check, or always performing the update when acctTimeDelta > 0, as shown in the recommended patch. This class of bug belongs to “incorrect state transition due to conditional guards” and manifests as a “refund calculation error” where users receive more tokens than they should, effectively causing funds to disappear from the contract’s accounting ledger. From a user’s perspective, the UI may display a normal balance after staking, but after a withdrawal the balance may unexpectedly increase beyond the deposited amount, contradicting the expectation that withdrawing should not yield extra tokens.

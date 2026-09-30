---
id: 21000
severity: "High"
---

# Taiko L1 - Proposer can maliciously cause loss of funds by forcing someone else to pay prover’s fee

## Description

Proposal of new blocks triggers a call to proposeBlock in the libProposing library. In that function, there is this the following block of code:

```solidity
if (params.coinbase == address(0)) {
    params.coinbase = msg.sender;
}
```

This sets the params.coinbase variable set by the caller of the function to be the msg.sender if it was empty.

As part of the process of proposal, hooks can be called of type AssignmentHook. An assignment hook’s onBlockProposed will be triggered as follows:

```solidity
// When a hook is called, all ether in this contract will be send to the hook.
// If the ether sent to the hook is not used entirely, the hook shall send the Ether
// back to this contract for the next hook to use.
// Proposers shall choose use extra hooks wisely.
IHook(params.hookCalls[i].hook).onBlockProposed{ value: address(this).balance }(
    blk, meta_, params.hookCalls[i].data
);
```

Notice how the meta data is passed to this function. Part of the function of the onBlockProposed is to pay the assigned prover their fee and the payee should be the current proposer of the block. this is done as follows:

```solidity
// The proposer irrevocably pays a fee to the assigned prover, either in
// Ether or ERC20 tokens.
if (assignment.feeToken == address(0)) {
    // Paying Ether
    _blk.assignedProver.sendEther(proverFee, MAX_GAS_PAYING_PROVER);
} else {
    // Paying ERC20 tokens
    IERC20(assignment.feeToken).safeTransferFrom(
        _meta.coinbase, _blk.assignedProver, proverFee
    );
}
```

Notice how if the payment is in ERC20 tokens, the payee will be the variable _meta.coinbase, and like we showed earlier, this can be set to any arbitrary address by the proposer. This can lead to a scenario as such:

1. proposer A approves the assignmentHook contract to spend a portion of their tokens, the allowance is set higher than the actual fee they will be paying.
2. proposer A proposes a block, and a fee is charged and paid to the assigned prover, but there remains allowance that the assignment hook contract can still use.
3. proposer B proposes a block and sets params.coinbase as the address of proposer A.
4. proposer A address will be the payee of the fee for the assigned prover for the block proposed by proposer B.

The scenario above describes how someone can be forced maliciously to pay fees for block proposals by other actors.

## Proof of Concept

no poc

## Recommendation

A simple fix to this to ensure the block proposer will always be the msg.sender, as such:

```solidity
if (params.coinbase == address(0) || params.coinbase != msg.sender) {
    params.coinbase = msg.sender;
}
```

This is a valid bug report. It has been fixed here: <https://github.com/taikoxyz/taiko-mono/pull/16327>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is an economic mis‑allocation bug that lets a block proposer force another address to pay the prover fee for a block proposal. In the block‑proposing flow the library copies the caller‑supplied params.coinbase into the internal metadata only when the field is zero, using the statement if (params.coinbase == address(0)) { params.coinbase = msg.sender; }. Because the check does not reject a non‑zero value, a malicious proposer can supply any address as coinbase. Later, when an AssignmentHook’s onBlockProposed callback pays the assigned prover, the contract uses the metadata field _meta.coinbase as the source of ERC20 token transfers: IERC20(assignment.feeToken).safeTransferFrom(_meta.coinbase, _blk.assignedProver, proverFee). Consequently the token transfer is taken from the address stored in coinbase, not from the proposer who triggered the hook. An attacker can therefore approve the hook contract to spend a large allowance of victim tokens, propose a block with the victim’s address as coinbase, and cause the victim’s allowance to be drained to pay the prover fee. The vulnerability manifests only when the fee is paid in ERC20 tokens and when the hook is invoked with a non‑zero coinbase value. It affects any user who has granted the hook contract a token allowance, as well as the protocol’s economic guarantees because fees may be paid by parties that never proposed a block. The bug was discovered during a security audit that examined the interaction between the proposing library and the AssignmentHook callback; the logic appeared harmless at first glance because the defaulting to msg.sender seemed reasonable, making the problem easy to overlook. From a user’s perspective the symptom is a sudden reduction of token balance after a block is proposed by someone else, contrary to the expectation that fees are only deducted from the proposer’s own account. The root cause is an improper validation of a user‑controlled address that is later used as the payer in a token transfer, a classic case of incorrect authorization or payment‑to‑arbitrary‑address vulnerability. To remediate, the contract should enforce that the coinbase field always equals msg.sender, ignoring any externally supplied value, for example by resetting the field whenever it does not match msg.sender. This ensures that only the actual proposer can be charged for the fee and prevents forced fee extraction from unrelated accounts.

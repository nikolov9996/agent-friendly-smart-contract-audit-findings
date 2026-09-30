---
id: 17669
severity: "High"
---

# OptimisticOracle.unbond can be tricked by malicious users

## Description

Malicious users can bypass the check of OptimisticOracle.unbond.
OptimisticOracle.unbond checks whether the current proposal has not been made by msg.sender.
```solidity
if (
    proposals[rateId] == proposalId &&
    rateConfig.validator != address(0) &&
    IValidator(rateConfig.validator).canDispute(nonce)
) {
    revert OptimisticOracle__unbond_isProposing();
}
```
However, nonce and value is given by msg.sender. So proposalId is determined by msg.sender.
```solidity
function unbond(
    bytes32 rateId,
    uint256 value,
    bytes32 nonce,
    address receiver
) public {
    bytes32 proposalId = computeProposalId(
        rateId,
        msg.sender,
        value,
        uint256(nonce)
    );
    // Current proposal has not been made by `msg.sender` or it has passed `disputeWindow`
    // or the rateConfig has been unset
    RateConfig memory rateConfig = rateConfigs[rateId];
    if (
        proposals[rateId] == proposalId &&
        rateConfig.validator != address(0) &&
        IValidator(rateConfig.validator).canDispute(nonce)
    ) {
        revert OptimisticOracle__unbond_isProposing();
    }
    ...
}
```
Thus, the check of proposalId can be easily bypassed.
Proposers can easily bypass the check in OptimisticOracle.unbond and successfully take back their bond tokens when they are in the dispute window.

## Proof of Concept

no poc

## Recommendation

Add a mapping for proposer and rateId: proposer[rateId] (Should be set in OptimisticOracle.shift).
Check proposer[rateId] instead of proposals[rateId].
```solidity
function unbond(
    bytes32 rateId,
    uint256 value,
    bytes32 nonce,
    address receiver
) public {
    bytes32 proposalId = computeProposalId(
        rateId,
        msg.sender,
        value,
        uint256(nonce)
    );
    // Current proposal has not been made by `msg.sender` or it has passed `disputeWindow`
    // or the rateConfig has been unset
    RateConfig memory rateConfig = rateConfigs[rateId];
    if (
        proposer[rateId] == msg.sender &&
        rateConfig.validator != address(0) &&
        IValidator(rateConfig.validator).canDispute(nonce)
    ) {
        revert OptimisticOracle__unbond_isProposing();
    }
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the unbond function of the OptimisticOracle contract. The function is supposed to prevent a proposer from retrieving the bond while a proposal is still within the dispute window. To enforce this, the code recomputes a proposal identifier (proposalId) from the caller address (msg.sender), the rate identifier, the bond value and a nonce, and then checks whether the stored proposal identifier for the given rate (proposals[rateId]) matches the recomputed one. If the identifiers match and a validator is configured, the call is reverted with OptimisticOracle__unbond_isProposing. Because the proposal identifier is derived from msg.sender, a malicious proposer can supply a different value or nonce that yields a different proposalId, causing the equality test to fail. Consequently the revert condition is bypassed and the function proceeds to release the bond even though the dispute window has not elapsed. The root cause is the reliance on a caller‑controlled identifier for the protection check instead of a stable record of who created the active proposal. The exploit can be carried out by any user who has previously submitted a proposal and still holds the bonded tokens; during the dispute period they simply call unbond with crafted parameters, the check does not trigger, and the contract releases the bonded tokens back to the attacker. The impact is that the economic guarantee that bonds provide against dishonest proposals is broken: attackers can reclaim their stake without waiting for the dispute window, potentially allowing them to submit multiple proposals without risk, undermining the oracle’s security model and exposing honest participants to loss of confidence and possible financial harm. The bug manifests only when a rate configuration includes a validator (rateConfig.validator != address(0)) and the validator reports that the proposal is still disputable (canDispute returns true). Under those conditions, the unbond function’s protective clause is ineffective. The issue was discovered during a manual security audit by the researcher Sherlock, who noticed that the proposal identifier is computed using msg.sender and therefore can be manipulated. It is subtle because the revert logic appears correct at a glance and typical unit tests may not vary the value or nonce parameters, making the bypass hard to detect in ordinary testing. To remediate the problem, the contract should store the proposer’s address in a dedicated mapping (e.g., proposer[rateId]) when a proposal is created and then compare msg.sender directly against that stored address in the unbond function, rather than recomputing a proposal identifier. This change ensures that the check cannot be evaded by altering input parameters, restoring the intended bond‑locking behavior and preserving the protocol’s economic security.

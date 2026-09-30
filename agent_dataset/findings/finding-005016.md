---
id: 5016
severity: "Critical"
---

# Faulty Access Control allows anyone to claim Fees

## Description

A Set's accumulated fees may be collected by calling the claimSetFees() function of the Manager singleton contract which allows an owner to batch-collect all fees from multiple of their Sets at once. To ensure that only the correct Set owner can claim these fees, the manager passes the msg.sender as parameter. The Set's claimSetFees() function then only needs to ensure that the current caller (msg.sender) is the Manager and the passed caller_ (i.e., who called the Manager's batch function) is the owner of the Set.
```solidity
contract Manager {
    /// @notice Transfers accrued set owner fees to the `receiver_` address.
    function claimSetFees(ISet[] calldata sets_, address receiver_) external {
        ...
        for (uint256 i = 0; i < sets_.length; i = i.inc()) {
            uint128 setOwnerFees_ = sets_[i].claimSetFees(msg.sender, receiver_);
            ...
        }
    }
}
```
```solidity
contract Set {
    /// @notice Transfers accrued Set Owner fees to the `receiver_` address.
    function claimSetFees(address caller_, address receiver_) external returns (uint128 setOwnerFees_) {
        if (msg.sender != address(manager) && caller_ != owner) revert Unauthorized();
        ...
    }
}
```
Due to a logic error, it instead allowed anyone to call the Set's claimSetFees() function directly as long as the caller_ specified matches the owner. Or alternatively, anyone could call the Manager's claimSetFees() without being the owner, as it was sufficient for the call to be made from the Manager. This faulty Access Control bug would have allowed anyone to specify themselves as _receiver and claim fees of Sets they do not have any ownership over.

## Proof of Concept

no poc

## Recommendation

The logic issue can be easily fixed:
```solidity
if (msg.sender != address(manager) || caller_ != owner) revert Unauthorized();
```
We also recommend the implementation of regression tests that make sure that calls to the claimSetFees() functions do indeed fail when they are supposed to.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect access‑control check in the fee‑claiming workflow of a manager‑set architecture. A manager contract provides a batch function that iterates over a list ofSet contracts and calls each Set’s claimSetFees method, passing the manager’s address as the caller identifier and a user‑specified receiver address. The Set contract is supposed to ensure that only the legitimate Set owner can receive the accumulated fees. It does this by checking two conditions: that the caller of claimSetFees is the manager contract, and that the supplied caller_ argument matches the stored owner address. However, the implementation uses a logical AND (&&) in the revert condition: if (msg.sender != manager && caller_ != owner) revert Unauthorized(). Because the revert only triggers when *both* the caller is not the manager *and* the supplied caller_ is not the owner, an attacker can bypass the check by either calling the manager’s batch function (where msg.sender equals the manager) or by calling the Set directly and supplying the owner’s address as caller_, even though the actual transaction sender is not the owner. Consequently, any address can specify itself as the receiver and withdraw fees that belong to a Set they do not own. The bug manifests whenever an external account invokes either the manager’s claimSetFees or the Set’s claimSetFees with a crafted caller_ argument. It affects all Set owners because their accrued fees can be siphoned by arbitrary parties, leading to loss of revenue and erosion of trust in the protocol. The issue was discovered during a manual security audit that examined the access‑control logic of the fee‑claim functions. It is subtle because the code appears to perform two checks, but the misuse of the logical operator creates a condition that is too permissive, making the flaw easy to overlook in casual testing. Exploitation is straightforward: an attacker calls the manager’s batch claim function with their own address as the receiver, or calls a Set directly with the owner’s address as the caller_ argument, and the contract transfers the fees to the attacker’s address. The impact is the unauthorized transfer of accumulated fees, effectively “funds disappear” from the rightful owner’s balance. To remediate, the condition should be inverted to require that *either* the caller is not the manager *or* the supplied caller_ is not the owner, i.e., if (msg.sender != manager || caller_ != owner) revert Unauthorized(). Adding regression tests that assert the function reverts when a non‑owner attempts to claim fees will help prevent regressions. This class of bug falls under improper authorization logic, where a combination of checks is incorrectly combined, allowing privilege escalation and theft of assets.

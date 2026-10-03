---
id: 25325
severity: "Low/Info"
---

# Throughout code-base: Homogenize how access control is done.

## Description

There are some discrepancies in the way that checks for access control/requires are done throughout the code base. Sometimes a modifier is used, sometimes an internal function is used, and sometimes the require is just hard-coded. Some examples below:

- on open-term/LoanManager.sol
- isLoan and notPaused are implemented as modifiers
- require is used to check if factory or if PD (Pool Delegate) or PM (Pool Manager)
- on fixed-term/LoanManager.sol
- internal function (_requireCallerIsPoolDelegate ) is used to check if PD (different from open-term above)
- internal function (_requireProtocolNotPaused) is used to check if protocol is not paused (different from open-term above)
- on open-term/MapleLoan.sol and on fixed-term/MapleLoan.sol
- whenNotPaused is used as a modifier
- require is used to check if factory, if borrower, if lender We understand that requires might be used to return custom string error messages that specify, in addition to the contract, in which function it reverted (which nevertheless is not

done in fixed-term LoanManager since internal functions are used here, where only the contract it reverts is specified in the error message); however, there is still a discrepancy on how the access control is done on the open-term and fixed-term for the LoanManager functions (internal functions vs requires).

## Proof of Concept

No PoC provided.

## Recommendation

We suggest using the same approach in both contracts. Also, there are three different implementations to check if a protocol is not paused (modifier notPaused, modifier whenNotPaused, internal function _requireProtocolNotPaused), we also suggest using the same approach across all contracts.

Additionally when a modifier is added to a function, the entire code of the modifier gets copied in all the functions. It is more gas efficient (on deployment) to implement the logic of the modifier in another function and call it from inside the modifier.

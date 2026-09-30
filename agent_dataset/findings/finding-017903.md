---
id: 17903
severity: "High"
---

# Attacker can take loan for Victim

## Description

An unapproved, non-owner of collateral can still take loan for the owner/operator of collateral even when owner did not needed any loan. This is happening due to incorrect checks as shown in POC. This leads to unintended loan and associated fees for users.

## Proof of Concept

1. A new loan is originated via `commitToLien` function by User X. Params used by User X are as below:

    collateralId = params.tokenContract.computeId(params.tokenId) = 1
    
    CT.ownerOf(1) = User Y
    
    CT.getApproved(1) = User Z
    
    CT.isApprovedForAll(User Y, User X) = false
    
    receiver = User Y

2. This internally make call to `_requestLienAndIssuePayout` which then calls `_validateCommitment` function for signature verification
3. Lets see the signature verification part in `_validateCommitment` function

```solidity
function _validateCommitment(
    IAstariaRouter.Commitment calldata params,
    address receiver
) internal view {
    uint256 collateralId = params.tokenContract.computeId(params.tokenId);
    ERC721 CT = ERC721(address(COLLATERAL_TOKEN()));
    address holder = CT.ownerOf(collateralId);
    address operator = CT.getApproved(collateralId);
    if (
        msg.sender != holder &&
        receiver != holder &&
        receiver != operator &&
        !CT.isApprovedForAll(holder, msg.sender)
    ) {
        revert InvalidRequest(InvalidRequestReason.NO_AUTHORITY);
    }
    VIData storage s = _loadVISlot();
    address recovered = ecrecover(
        keccak256(
            _encodeStrategyData(
                s,
                params.lienRequest.strategy,
                params.lienRequest.merkle.root
            )
        ),
        params.lienRequest.v,
        params.lienRequest.r,
        params.lienRequest.s
    );
    if (
        (recovered != owner() && recovered != s.delegate) ||
        recovered == address(0)
    ) {
        revert IVaultImplementation.InvalidRequest(
            InvalidRequestReason.INVALID_SIGNATURE
        );
    }
}
```

4. Ideally the verification should fail since :

a. User X is not owner of passed collateral  
b. User X is not approved for this collateral  
c. User X is not approved for all of User Y token

5. But observe the below if condition doing the required check:

```solidity
uint256 collateralId = params.tokenContract.computeId(params.tokenId);
ERC721 CT = ERC721(address(COLLATERAL_TOKEN()));
address holder = CT.ownerOf(collateralId);
address operator = CT.getApproved(collateralId);
if (
    msg.sender != holder &&
    receiver != holder &&
    receiver != operator &&
    !CT.isApprovedForAll(holder, msg.sender)
) {
    revert InvalidRequest(InvalidRequestReason.NO_AUTHORITY);
}
```

6. In our case this if condition does not execute since receiver = holder

```solidity
if (
    msg.sender != holder && // true since User X is not the owner
    receiver != holder && // false since attacker passed receiver as User Y which is owner of collateral, thus failing this if condition 
    receiver != operator &&
    !CT.isApprovedForAll(holder, msg.sender)
) {
    revert InvalidRequest(InvalidRequestReason.NO_AUTHORITY);
}
```

7. This means the signature verification passes and loan is issued for collateral owner without his wish

## Recommendation

Revise the condition as shown below:
    
```solidity
if (
    msg.sender != holder &&
    msg.sender != operator &&
    !CT.isApprovedForAll(holder, msg.sender)
) {
    revert InvalidRequest(InvalidRequestReason.NO_AUTHORITY);
}

if (
    receiver != holder &&
    receiver != operator 
) {
    revert InvalidRequest(InvalidRequestReason.NO_AUTHORITY);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization bypass that allows an attacker who does not own or have explicit permission for a piece of collateral to initiate a loan on behalf of the legitimate owner. The root cause lies in the logical condition that validates who may request a loan. The contract checks that either the caller (msg.sender) is the collateral holder, the designated receiver is the holder, the receiver is the approved operator, or the caller is approved for all of the holder’s tokens. Because the condition combines these checks with logical AND, an attacker can satisfy the test simply by setting the receiver address to the actual owner of the collateral. In that case the sub‑condition `receiver != holder` evaluates to false, causing the whole `if` statement to be skipped even though the caller is neither the owner nor an approved operator. Consequently the signature verification proceeds and the loan is issued, charging fees to the unsuspecting owner. Exploitation proceeds as follows: (1) the attacker calls the loan‑creation function with a collateral identifier they do not control; (2) they set the `receiver` parameter to the true owner’s address; (3) the contract’s authority check evaluates to false because the receiver matches the holder; (4) the contract skips the revert and creates a lien, minting a loan and associated debt against the owner’s collateral. The impact is that the victim’s account accrues an unwanted loan, incurs interest and fees, and may face liquidation or loss of collateral value. Any user who holds ERC‑721 collateral, as well as the protocol’s overall accounting and lenders, can be affected because the protocol records debt that was never authorized. The issue was discovered during a security audit when the auditors examined the `_validateCommitment` function and noticed that the condition incorrectly mixes `msg.sender` and `receiver` checks, allowing the bypass. It is subtle because the code appears to protect the owner at first glance, but the logical operator ordering creates a loophole that is not obvious without tracing the exact evaluation path. To remediate, the contract should enforce that the caller is authorized independently of the receiver, for example by rejecting the request unless `msg.sender` is the holder, an approved operator, or approved for all, and additionally ensuring that the `receiver` is also authorized or equal to the caller. In other words, the authority check must be split into two distinct validations: one for the transaction initiator and one for the designated loan recipient, preventing an attacker from masquerading as the owner by merely setting the receiver field. This class of bug is an improper access control check, often referred to as an authorization bypass due to flawed logical conditions. From the user’s perspective the symptom is a sudden loan appearing on their account, a debt balance that was never requested, and unexpected fee deductions, contradicting the expectation that a loan is only created when they explicitly initiate it.

---
id: 19779
severity: "High"
---

# Unlinked tophat retains linkedTreeRequests,

## Description

When a tophat is unlinked from its admin, it is intended to regain its status as a tophat that is fully self-sovereign. However, because the linkedTreeRequests value isn't deleted, an independent tophat could still be vulnerable to "takeover" from another admin and could lose its sovereignty.
For a tophat to get linked to a new tree, it calls requestLinkTopHatToTree() function:
```solidity
function requestLinkTopHatToTree(uint32 _topHatDomain, uint256 _requestedAdminHat) external {
    uint256 fullTopHatId = uint256(_topHatDomain) << 224; // (256 - TOPHAT_ADDRESS_SPACE);
    _checkAdmin(fullTopHatId);
    linkedTreeRequests[_topHatDomain] = _requestedAdminHat;
    emit TopHatLinkRequested(_topHatDomain, _requestedAdminHat);
}
```
This creates a "request" to link to a given admin, which can later be approved by the admin in question:
```solidity
function approveLinkTopHatToTree(uint32 _topHatDomain, uint256 _newAdminHat) external {
    // for everything but the last hat level, check the admin of `_newAdminHat`'s theoretical child hat, since either wearer or admin of `_newAdminHat` can approve
    if (getHatLevel(_newAdminHat) < MAX_LEVELS) {
        _checkAdmin(buildHatId(_newAdminHat, 1));
    } else {
        // the above buildHatId trick doesn't work for the last hat level, so we need to explicitly check both admin and wearer in this case
        _checkAdminOrWearer(_newAdminHat);
    }
    // Linkages must be initiated by a request
    if (_newAdminHat != linkedTreeRequests[_topHatDomain]) revert LinkageNotRequested();
    // remove the request -- ensures all linkages are initialized by unique requests, except for relinks (see `relinkTopHatWithinTree`)
    delete linkedTreeRequests[_topHatDomain];
    // execute the link. Replaces existing link, if any.
    _linkTopHatToTree(_topHatDomain, _newAdminHat);
}
```
This function shows that if there is a pending linkedTreeRequests, then the admin can use that to link the tophat into their tree and claim authority over it.
When a tophat is unlinked, it is expected to regain its sovereignty:
```solidity
function unlinkTopHatFromTree(uint32 _topHatDomain) external {
    uint256 fullTopHatId = uint256(_topHatDomain) << 224; // (256 - TOPHAT_ADDRESS_SPACE);
    _checkAdmin(fullTopHatId);
    delete linkedTreeAdmins[_topHatDomain];
    emit TopHatLinked(_topHatDomain, 0);
}
```
However, this function does not delete linkedTreeRequests.
Therefore, the following set of actions is possible:
• TopHat is linked to Admin A
• Admin A agrees to unlink the tophat
• Admin A calls requestLinkTopHatToTree with any address as the admin
• This call succeeds because Admin A is currently an admin for TopHat
• Admin A unlinks TopHat as promised
• In the future, the address chosen can call approveLinkTopHatToTree and take over admin controls for the TopHat without the TopHat's permission
Tophats that expect to be fully self-sovereign and without any oversight can be surprisingly claimed by another admin, because settings from a previous admin remain through unlinking.

## Proof of Concept

no poc

## Recommendation

In unlinkTopHatFromTree(), the linkedTreeRequests should be deleted:
```solidity
function unlinkTopHatFromTree(uint32 _topHatDomain) external {
    uint256 fullTopHatId = uint256(_topHatDomain) << 224; // (256 - TOPHAT_ADDRESS_SPACE);
    _checkAdmin(fullTopHatId);
    delete linkedTreeAdmins[_topHatDomain];
    delete linkedTreeRequests[_topHatDomain];
    emit TopHatLinked(_topHatDomain, 0);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the unlinkTopHatFromTree function, which is intended to restore a tophat’s full self‑sovereignty after it has been detached from an admin tree. While the function correctly deletes the linkedTreeAdmins entry, it fails to clear the linkedTreeRequests mapping that stores a pending request to link the tophat to a new admin. Because the request remains in storage, a previously authorized admin (or any address that knows the request value) can later call approveLinkTopHatToTree and successfully link the tophat to their own hat, thereby hijacking admin control without the tophat’s consent. The root cause is a stale state – a leftover permission request that is not removed during the unlink operation. Exploitation proceeds by first having the current admin create a link request via requestLinkTopHatToTree, then unlinking the tophat, after which the request persists. At a later time the same admin or a malicious actor invokes approveLinkTopHatToTree, passing the stored request identifier, which passes the linkage check and re‑establishes admin authority. The impact is a loss of sovereignty for the tophat owner: the hat that was expected to be independent can be taken over, potentially compromising governance decisions, fund management, or any privileged actions tied to the hat. This occurs whenever a tophat is unlinked while a link request is pending, which can happen for any domain that has previously been linked. The affected parties include the hat owners, protocol participants relying on the hat’s autonomy, and any users whose assets or permissions are governed by the hat. The issue was discovered during a manual audit of the contract’s state‑reset logic, where the unlink function was examined and the omission of linkedTreeRequests was noted. The bug is subtle because the unlink transaction emits an event indicating the hat is now linked to zero, giving the impression that all relationships have been cleared, while the hidden request remains invisible to most front‑ends. From a user’s perspective the symptom is that after unlinking, the hat appears to have no admin, yet later the admin role is suddenly assigned to an unexpected address, resulting in “admin rights disappear and reappear under a stranger”. The expectation that unlinking fully isolates the hat is violated, breaking the accounting assumption that no pending linkage survives a detach operation. The recommended remediation is to delete the linkedTreeRequests entry in the unlinkTopHatFromTree function, ensuring that all pending linkage state is cleared and the hat truly regains self‑sovereignty. This class of bug is a stale state or leftover permission request that enables privilege escalation, similar to other cases where state is not fully reset after a role change.

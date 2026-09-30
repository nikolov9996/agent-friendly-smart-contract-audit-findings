---
id: 16779
severity: "High"
---

# ERC721Votes’s delegation disables NFT transfers and burning

## Description

If Alice the NFT owner first delegates her votes to herself, second delegates to anyone else with delegate() or delegateBySig() then all her NFT ids will become stuck: their transfers and burning will be disabled.

The issue is _afterTokenTransfer() callback running the _moveDelegateVotes() with an owner instead of her delegate. As Alice’s votes in the checkpoint is zero after she delegated them, the subtraction _moveDelegateVotes() tries to perform during the move of the votes will be reverted.

As ERC721Votes is parent to Token and delegate is a kind of common and frequent operation, the impact is governance token moves being frozen in a variety of use cases, which interferes with governance voting process and can be critical for the project.

## Proof of Concept

Suppose Alice delegated all her votes to herself and then decided to delegate them to someone else with either delegate() or delegateBySig() calling _delegate():

```solidity
function _delegate(address _from, address _to) internal {
    // Get the previous delegate
    address prevDelegate = delegation[_from];

    // Store the new delegate
    delegation[_from] = _to;

    emit DelegateChanged(_from, prevDelegate, _to);

    // Transfer voting weight from the previous delegate to the new delegate
    _moveDelegateVotes(prevDelegate, _to, balanceOf(_from));
}
```

_moveDelegateVotes() will set her votes to `0` as `_from == Alice` and `prevTotalVotes = _amount = balanceOf(Alice)` (as _afterTokenTransfer() incremented Alice’s vote balance on each mint to her):

```solidity
function _moveDelegateVotes(
    address _from,
    address _to,
    uint256 _amount
) internal {
    unchecked {
        // If voting weight is being transferred:
        if (_from != _to && _amount > 0) {
            // If this isn't a token mint:
            if (_from != address(0)) {
                // Get the sender's number of checkpoints
                uint256 nCheckpoints = numCheckpoints[_from]++;

                // Used to store the sender's previous voting weight
                uint256 prevTotalVotes;

                // If this isn't the sender's first checkpoint: Get their previous voting weight
                if (nCheckpoints != 0) prevTotalVotes = checkpoints[_from][nCheckpoints - 1].votes;

                // Update their voting weight
                _writeCheckpoint(_from, nCheckpoints, prevTotalVotes, prevTotalVotes - _amount);
            }
```

After that her votes in the checkpoint become zero. She will not be able to transfer the NFT as `_afterTokenTransfer` will revert on `_moveDelegateVotes`’s attempt to move `1` vote from `Alice` to `_to`, while `checkpoints[Alice][nCheckpoints - 1].votes` is `0`:

```solidity
function _afterTokenTransfer(
    address _from,
    address _to,
    uint256 _tokenId
) internal override {
    // Transfer 1 vote from the sender to the recipient
    _moveDelegateVotes(_from, _to, 1);
```

## Recommendation

The root issue is _afterTokenTransfer() dealing with Alice instead of Alice’s delegate.

Consider including delegates() call as a fix:

```solidity
function _afterTokenTransfer(
    address _from,
    address _to,
    uint256 _tokenId
) internal override {
    // Transfer 1 vote from the sender to the recipient
    _moveDelegateVotes(delegates(_from), delegates(_to), 1);
```

As `delegates(address(0)) == address(0)` the burning/minting flow will persist:

```solidity
/// @notice The delegate for an account
/// @param _account The account address
function delegates(address _account) external view returns (address) {
    address current = delegation[_account];
    return current == address(0) ? _account : current;
}
```

The Warden has shown how, due to the overlapping system handling delegation and balances, it is possible for a user to brick their own `transferability` of their tokens.

This POC shows that any delegation will cause the issues as when dealing with a transfer, their currently zero-vote-balance will further be deducted instead of the delegated votes they have.

Because the finding shows a broken invariant, in that any delegation will brick transfers, as the invariants offered by ERC721Votes have been broken; I believe High Severity to be appropriate.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the ERC721Votes extension that couples NFT ownership with a voting power tracking system. In a normal flow, when an ERC721 token is transferred, the internal hook _afterTokenTransfer calls _moveDelegateVotes to shift one voting unit from the sender’s current delegate to the receiver’s delegate. The contract incorrectly uses the raw token owner address (_from and _to) as the source and destination of the vote movement instead of querying each address’s active delegate via the delegates() function. This mistake becomes critical when a token holder first delegates her voting power to herself and later re‑delegates it to another address using delegate() or delegateBySig(). The first delegation sets the holder’s vote balance to zero in the checkpoint history because the votes are transferred from the holder (who is also the delegate) to the new delegate. Once the holder’s recorded votes are zero, any subsequent token transfer triggers the _afterTokenTransfer hook, which again tries to move one vote from the holder’s address – now holding zero voting power – to the recipient. The _moveDelegateVotes routine enforces that the source has sufficient votes, detects the zero balance, and reverts the transaction. As a result, all NFTs owned by the affected address become permanently non‑transferable and non‑burnable; the contract will reject any attempt to move or destroy those tokens. From a user perspective, the symptoms are stark: the UI shows the token in the wallet, but a transfer or burn action fails silently or returns a generic “transaction reverted” error, leaving the user unable to move or sell the asset. The issue was uncovered during a security audit that exercised delegation patterns and observed that after a self‑delegation followed by a delegation change, the token could no longer be transferred. The bug is difficult to notice because the delegation functions themselves succeed, and the failure only appears later during a transfer, a scenario that may not be covered by typical unit tests. Conceptually, the problem is a broken invariant between token ownership and voting delegation: the contract assumes the owner’s votes are always available for movement, which is false once the owner’s vote balance has been cleared by a delegation. The fix involves adjusting the _afterTokenTransfer hook to reference the current delegate of each address (using delegates(_from) and delegates(_to)) rather than the raw owner addresses, and ensuring that the delegate query returns the owner itself when no explicit delegate is set. By restoring the proper linkage between ownership and delegated voting power, the transfer and burn pathways regain their expected behavior, and the governance token remains functional across typical delegation workflows.

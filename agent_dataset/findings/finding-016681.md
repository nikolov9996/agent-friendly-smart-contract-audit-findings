---
id: 16681
severity: "High"
---

# ERC721Checkpointable: delegateBySig allows the user to vote to address 0, which causes the user to permanently lose his vote and cannot transfer his NFT.

## Description

In the ERC721Checkpointable contract, when the user votes with the delegate function, the delegatee will not be address 0.

```solidity
function delegate(address delegatee) public {
    if (delegatee == address(0)) delegatee = msg.sender;
    return _delegate(msg.sender, delegatee);
}
```

However, there is no such restriction in the delegateBySig function, which allows the user to vote to address 0.

```solidity
function delegateBySig(
    address delegatee,
    uint256 nonce,
    uint256 expiry,
    uint8 v,
    bytes32 r,
    bytes32 s
) public {
    bytes32 domainSeparator = keccak256(
        abi.encode(DOMAIN_TYPEHASH, keccak256(bytes(name())), getChainId(), address(this))
    );
    bytes32 structHash = keccak256(abi.encode(DELEGATION_TYPEHASH, delegatee, nonce, expiry));
    bytes32 digest = keccak256(abi.encodePacked('\x19\x01', domainSeparator, structHash));
    address signatory = ecrecover(digest, v, r, s);
    require(signatory != address(0), 'ERC721Checkpointable::delegateBySig: invalid signature');
    require(nonce == nonces[signatory]++, 'ERC721Checkpointable::delegateBySig: invalid nonce');
    require(block.timestamp <= expiry, 'ERC721Checkpointable::delegateBySig: signature expired');
    return _delegate(signatory, delegatee);
}
```

If user A votes to address 0 in the delegateBySig function, _delegates[A] will be address 0, but the delegates function will return the address of user A and getCurrentVotes(A) will return 0.

```solidity
function _delegate(address delegator, address delegatee) internal {
    /// @notice differs from `_delegate()` in `Comp.sol` to use `delegates` override method to simulate auto-delegation
    address currentDelegate = delegates(delegator);

    _delegates[delegator] = delegatee;
...
function delegates(address delegator) public view returns (address) {
    address current = _delegates[delegator];
    return current == address(0) ? delegator : current;
}
```

Later, if user A votes to another address or transfers NFT, the _moveDelegates function will fail due to overflow, which makes user A lose votes forever and cannot transfer NFT.

```solidity
function _moveDelegates(
    address srcRep,
    address dstRep,
    uint96 amount
) internal {
    if (srcRep != dstRep && amount > 0) {
        if (srcRep != address(0)) {
            uint32 srcRepNum = numCheckpoints[srcRep];
            uint96 srcRepOld = srcRepNum > 0 ? checkpoints[srcRep][srcRepNum - 1].votes : 0;
            uint96 srcRepNew = sub96(srcRepOld, amount, 'ERC721Checkpointable::_moveDelegates: amount underflows'); // auditor : overflow here
            _writeCheckpoint(srcRep, srcRepNum, srcRepOld, srcRepNew);
        }
```

On the other hand, since the burn function also fails, this can also be used to prevent the NFT from being burned by the minter

```solidity
function burn(uint256 nounId) public override onlyMinter {
    _burn(nounId);
    emit NounBurned(nounId);
}
...
function _burn(uint256 tokenId) internal virtual {
    address owner = ERC721.ownerOf(tokenId);

    _beforeTokenTransfer(owner, address(0), tokenId);
...
function _beforeTokenTransfer(
    address from,
    address to,
    uint256 tokenId
) internal override {
    super._beforeTokenTransfer(from, to, tokenId);

    /// @notice Differs from `_transferTokens()` to use `delegates` override method to simulate auto-delegation
    _moveDelegates(delegates(from), delegates(to), 1);
}
```

## Proof of Concept

no poc

## Recommendation

Consider requiring in the `delegateBySig` function that delegatee cannot be address 0.

```solidity
function delegateBySig(
    address delegatee,
    uint256 nonce,
    uint256 expiry,
    uint8 v,
    bytes32 r,
    bytes32 s
) public {
    require(delegatee != address(0));
```

We agree this is a bug that has existed since Nouns launched, and plan to fix the bug with the suggested requirement that delegatee should not be address(0).

Worth noting that this fix will not have a positive effect on Nouns, as the token is already deployed and not upgradable.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the ERC721Checkpointable contract’s off‑chain delegation mechanism, specifically the `delegateBySig` function. Unlike the on‑chain `delegate` function, which sanitises the `delegatee` argument by redirecting a zero address to the caller, `delegateBySig` lacks any check that prevents a caller from submitting a signed delegation to the zero address (0x0). When a holder executes `delegateBySig` with `delegatee = address(0)`, the internal `_delegate` routine stores this zero address directly in the `_delegates` mapping. The public `delegates` view function later interprets a stored zero as a fallback to the delegator only for calls that go through `delegate`, but because the zero value is now persisted, subsequent calls to `_moveDelegates`—which update voting checkpoints during transfers or further delegations—receive an invalid source representative. The arithmetic in `_moveDelegates` attempts to subtract the transferred amount from a source vote count that is already zero, triggering an underflow overflow (`sub96` reverts). This revert aborts the transfer logic, effectively locking the NFT: the holder can no longer transfer, delegate to another address, or even burn the token. From a user’s perspective the symptoms are a sudden disappearance of voting power (the UI shows zero votes), transaction failures with generic “amount underflows” errors, and an inability to move or destroy the NFT. The issue was uncovered during a Code4rena audit by analysing the logical divergence between `delegate` and `delegateBySig`. It is hard to notice because the contract does not emit a distinct error for delegating to zero; the failure only surfaces later when a state‑changing operation attempts to move votes. The bug belongs to the class of input‑validation errors that lead to inconsistent internal state and arithmetic underflow. The recommended remediation is to add a `require(delegatee != address(0))` guard to `delegateBySig`, or to adjust the internal delegate handling so that a zero address is treated the same as in `delegate`. While the contract is already deployed and not upgradable, the fix would prevent future occurrences of permanent vote loss and transfer blockage.

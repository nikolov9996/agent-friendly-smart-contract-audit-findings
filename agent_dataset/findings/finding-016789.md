---
id: 16789
severity: "High"
---

# `ERC721Votes`: Token owners can double voting power through self delegation

## Description

The owner of one or many `ERC721Votes` tokens can double their voting power once (and only once) by delegating to their own address as their first delegation.

## Proof of Concept

This exploit relies on the initial default value of the `delegation` mapping in `ERC721Votes`, which is why it will only work once per address.

First, the token owner must call `delegate` or `delegateBySig`, passing their own address as the delegate:

[`ERC721Votes#delegate`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L131-L135)
    
```solidity
        /// @notice Delegates votes to an account
        /// @param _to The address delegating votes to
        function delegate(address _to) external {
            _delegate(msg.sender, _to);
        }
```

This calls into the internal `_delegate` function, with `_from` and `_to` both set to the token owner’s address:

[`ERC721Votes#_delegate`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L176-L190)
    
```solidity
        /// @dev Updates delegate addresses
        /// @param _from The address delegating votes from
        /// @param _to The address delegating votes to
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

Since this is the token owner’s first delegation, the `delegation` mapping does not contain a value for the `_from` address, and `prevDelegate` on L#181 will be set to `address(0)`:

[`ERC721Votes.sol#L180-L181`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L180-L181)
    
```solidity
            // Get the previous delegate
            address prevDelegate = delegation[_from];
```

This function then calls into `_moveDelegateVotes` to transfer voting power. This time, `_from` is `prevDelegate`, equal to `address(0)`; `_to` is the token owner’s address; and `_amount` is `balanceOf(_from)`, the token owner’s current balance:

[`ERC721Votes#_moveDelegateVotes`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L192-L235)
    
```solidity
     /// @dev Transfers voting weight
        /// @param _from The address delegating votes from
        /// @param _to The address delegating votes to
        /// @param _amount The number of votes delegating
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
    
                    // If this isn't a token burn:
                    if (_to != address(0)) {
                        // Get the recipients's number of checkpoints
                        uint256 nCheckpoints = numCheckpoints[_to]++;
    
                        // Used to store the recipient's previous voting weight
                        uint256 prevTotalVotes;
    
                        // If this isn't the recipient's first checkpoint: Get their previous voting weight
                        if (nCheckpoints != 0) prevTotalVotes = checkpoints[_to][nCheckpoints - 1].votes;
    
                        // Update their voting weight
                        _writeCheckpoint(_to, nCheckpoints, prevTotalVotes, prevTotalVotes + _amount);
                    }
                }
            }
        }
```

The `if` condition on L#203 is `true`, since `_from` is `address(0)`, `_to` is the owner address, and `_amount` is nonzero:

[`ERC721Votes.sol#L202-L203`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L202-L203)
    
```solidity
                // If voting weight is being transferred:
                if (_from != _to && _amount > 0) {
```

Execution skips the `if` block on L#205-217, since `_from` is `address(0)`:

[`ERC721Votes.sol#L205-L217`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L204-L217)
    
```solidity
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

However, the `if` block on L#220-232 will execute and increase the voting power allocated to `_to`:

[`ERC721Votes.sol#L220-L232`](https://github.com/code-423n4/2022-09-nouns-builder/blob/7e9fddbbacdd7d7812e912a369cfd862ee67dc03/src/lib/token/ERC721Votes.sol#L219-L232)
    
```solidity
                    // If this isn't a token burn:
                    if (_to != address(0)) {
                        // Get the recipients's number of checkpoints
                        uint256 nCheckpoints = numCheckpoints[_to]++;
    
                        // Used to store the recipient's previous voting weight
                        uint256 prevTotalVotes;
    
                        // If this isn't the recipient's first checkpoint: Get their previous voting weight
                        if (nCheckpoints != 0) prevTotalVotes = checkpoints[_to][nCheckpoints - 1].votes;
    
                        // Update their voting weight
                        _writeCheckpoint(_to, nCheckpoints, prevTotalVotes, prevTotalVotes + _amount);
                    }
```

The token owner’s voting power has now been increased by an amount equal to their total number of tokens, without an offsetting decrease.

This exploit only works once: if a token owner subsequently delegates to themselves after their initial self delegation, `prevDelegate` will be set to a non-default value in `_delegate`, and the delegation logic will work as intended.

(Put the following test cases in `Gov.t.sol`)
    
```solidity
        function test_delegate_to_self_doubles_voting_power() public {
            mintVoter1();
    
            assertEq(token.getVotes(address(voter1)), 1);
    
            vm.startPrank(voter1);
            token.delegate(address(voter1));
    
            assertEq(token.getVotes(address(voter1)), 2);
        }
    
        function mintToken(uint256 tokenId) internal {
            vm.prank(voter1);
            auction.createBid{ value: 0.420 ether }(tokenId);
    
            vm.warp(block.timestamp + auctionParams.duration + 1 seconds);
            auction.settleCurrentAndCreateNewAuction();
        }
    
        function test_delegate_to_self_multiple_tokens_doubles_voting_power() public {
            // An especially malicious user may acquire multiple tokens
            // before doubling their voting power through this exploit.
            mintVoter1();
            mintToken(3);
            mintToken(4);
            mintToken(5);
            mintToken(6);
    
            assertEq(token.getVotes(address(voter1)), 5);
    
            vm.prank(voter1);
            token.delegate(address(voter1));
    
            assertEq(token.getVotes(address(voter1)), 10);
        }
```

The warden has shown how, because of an incorrect assumption in reducing a non-existing previous delegate votes, through self-delegation, a user can double their voting power.
 
Because the finding shows how the delegation system is broken, and because governance is a core aspect (Secure funds, move funds, etc..) I agree with High Severity.
 
Due to multiple reports of this type, with various different attacks, mitigation is non-trivial.

In contrast to the dangerous overflow, this finding (and its duplicates) has shown how the Delegation Mechanism can be used to double the voting power.
 
For that reason, the underlying issue being different, am choosing to leave this finding separate.

## Recommendation

Make the `delegates` function `public` rather than `external`:
    
```solidity
        /// @notice The delegate for an account
        /// @param _account The account address
        function delegates(address _account) public view returns (address) {
            address current = delegation[_account];
            return current == address(0) ? _account : current;
        }
```

Then, call this function rather than accessing the `delegation` mapping directly:
    
```solidity
        /// @dev Updates delegate addresses
        /// @param _from The address delegating votes from
        /// @param _to The address delegating votes to
        function _delegate(address _from, address _to) internal {
            // Get the previous delegate
            address prevDelegate = delegates(_from);
    
            // Store the new delegate
            delegation[_from] = _to;
    
            emit DelegateChanged(_from, prevDelegate, _to);
    
            // Transfer voting weight from the previous delegate to the new delegate
            _moveDelegateVotes(prevDelegate, _to, balanceOf(_from));
        }
```

Note that the original NounsDAO contracts follow this pattern. (See [here](https://github.com/nounsDAO/nouns-monorepo/blob/master/packages/nouns-contracts/contracts/base/ERC721Checkpointable.sol#L83-L91) and [here](https://github.com/nounsDAO/nouns-monorepo/blob/master/packages/nouns-contracts/contracts/base/ERC721Checkpointable.sol#L83-L91)).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a delegation‑logic error in ERC721Votes contracts that allows a token holder to double their voting power by performing a self‑delegation as their first delegation. The root cause is that the internal _delegate function reads the raw delegation mapping to obtain the previous delegate (prevDelegate) without considering the default state of the mapping. When an address has never delegated before, the mapping entry is zero, so prevDelegate is address(0). The subsequent call to _moveDelegateVotes transfers the full token balance from the zero address to the delegating address, increasing the recipient’s checkpointed votes without ever decrementing any other account because the zero address is treated as a mint operation. As a result, the owner’s vote count becomes the sum of their original voting weight plus the same amount again, effectively doubling it. This exploit can be carried out by invoking the public delegate() or delegateBySig() function with the caller’s own address as the delegate argument. Because the contract only checks that _from != _to and that _amount > 0, the condition passes and the vote increase is applied. The attack succeeds only once per address, because after the first self‑delegation the delegation mapping stores a non‑zero value, causing subsequent self‑delegations to follow the correct path where the previous delegate’s votes are correctly reduced. The impact is a material inflation of voting power for any token holder who performs the self‑delegation, allowing them to sway governance proposals, potentially approve malicious actions, or move protocol funds that rely on quorum or vote thresholds. The bug manifests under the condition that an address with ERC721Votes holdings calls delegate() for the first time and passes its own address as the delegate. It affects all token owners, any governance participants, and ultimately the protocol’s security guarantees. The issue was uncovered during a Code4rena audit through targeted unit tests that compared vote counts before and after a self‑delegation. It may be hard to notice because vote counts appear correct after one delegation and only the first self‑delegation causes an unexpected increase; without a baseline comparison many participants would not detect the extra votes. The vulnerability belongs to the class of delegation or voting‑weight accounting bugs where the system fails to properly subtract weight from a previous delegate when that delegate is the zero address, resulting in double‑counting. From a user’s perspective, the UI may show a higher vote total than the number of tokens owned – the user expects one vote per token but sees two votes per token after self‑delegation, leading to confusion. To remediate the issue, the contract should obtain the previous delegate through a public delegates() accessor that returns the caller’s address when no explicit delegation exists, and use that value to correctly compute vote transfers, ensuring that the zero‑address case does not create new voting power. Alternatively, the _delegate logic can be adjusted to treat address(0) as a no‑op for vote subtraction or to explicitly prevent self‑delegation as the first action. Properly fixing the delegation handling restores the invariant that total voting power across all accounts always equals the total token supply, preserving the integrity of governance mechanisms.

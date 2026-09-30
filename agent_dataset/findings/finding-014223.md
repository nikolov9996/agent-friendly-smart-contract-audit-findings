---
id: 14223
severity: "High"
---

# Fund will be stuck if a buyout is started while there are pending migration proposals

## Description

Funds in migration proposals could potentially be stuck forever if a buyout auction on the same vault is started by other party.

Most of the functions within `Migration.sol` can only be executed depending on the state of buyout auction in `Buyout.sol`. When there is no buyout happening, a migration proposal can be made and anyone can contribute to the proposal. However, it is possible that a buyout auction is started by another party while a pending proposal is not commited yet.

When this scenario happens, there is no action that could be taken to interact with the pending proposal. All funds that have been contributed cannot be withdrawn. This is because the functions only check for the state of the buyout auction, instead of also considering whether the buyout auction’s proposer is `Migration.sol`:

```solidity
(address token, uint256 id) = IVaultRegistry(registry).vaultToToken(_vault);
if (id == 0) revert NotVault(_vault);
// Reverts if buyout state is not inactive
(, , State current, , , ) = IBuyout(buyout).buyoutInfo(_vault);
State required = State.INACTIVE;
if (current != required) revert IBuyout.InvalidState(required, current);
```

Proposal contributors have to wait until the buyout failed before they can withdraw their funds. In case the buyout succeeded, their funds will be stuck forever.

## Proof of Concept

* Bob made a migration proposal and contributed `0.5 eth`.
  * Alice individually started a buyout auction. Buyout state is now `ACTIVE`.
  * Bob can’t leave the proposal.
  * Alice successfully ended the buyout auction. Buyout state is now `SUCCESS`.
  * Bob can’t withdraw the funds.

Below are the test cases that show the scenarios described above.

```solidity
function testLeaveBuyoutStarted() public {
    initializeMigration(alice, bob, TOTAL_SUPPLY, HALF_SUPPLY, true);
    (nftReceiverSelectors, nftReceiverPlugins) = initializeNFTReceiver();
    // Migrate to a vault with no permissions (just to test out migration)
    address[] memory modules = new address[](1);
    modules[0] = address(mockModule);
    // Bob makes the proposal
    bob.migrationModule.propose(
        vault,
        modules,
        nftReceiverPlugins,
        nftReceiverSelectors,
        TOTAL_SUPPLY * 2,
        1 ether
    );
    // Bob joins the proposal
    bob.migrationModule.join{value: 0.5 ether}(vault, 1, HALF_SUPPLY);

    // Alice started buyout
    alice.buyoutModule.start{value: 1 ether}(vault);
    (, , State current, , , ) = alice.buyoutModule.buyoutInfo(vault);
    assert(current == State.LIVE);

    vm.expectRevert(
        abi.encodeWithSelector(IBuyout.InvalidState.selector, 0, 1)
    );
    // Bob cannot leave
    bob.migrationModule.leave(vault, 1);
}

function testLeaveBuyoutSuccess() public {
    // Send Bob a smaller amount so Alice can win the auction
    initializeMigration(alice, bob, TOTAL_SUPPLY, HALF_SUPPLY/2, true);
    (nftReceiverSelectors, nftReceiverPlugins) = initializeNFTReceiver();
    // Migrate to a vault with no permissions (just to test out migration)
    address[] memory modules = new address[](1);
    modules[0] = address(mockModule);
    // Bob makes the proposal
    bob.migrationModule.propose(
        vault,
        modules,
        nftReceiverPlugins,
        nftReceiverSelectors,
        TOTAL_SUPPLY * 2,
        1 ether
    );
    // Bob joins the proposal
    bob.migrationModule.join{value: 0.5 ether}(vault, 1, HALF_SUPPLY/2);

    // Alice did a buyout
    alice.buyoutModule.start{value: 1 ether}(vault);
    vm.warp(rejectionPeriod + 1);
    alice.buyoutModule.end(vault, burnProof);

    (, , State current, , , ) = alice.buyoutModule.buyoutInfo(vault);
    assert(current == State.SUCCESS);

    vm.expectRevert(
        abi.encodeWithSelector(IBuyout.InvalidState.selector, 0, 2)
    );
    // Bob cannot leave
    bob.migrationModule.leave(vault, 1);
}
```

## Recommendation

Modify the checks for the following functions:

  * `leave`
  * `withdrawContribution`

So users can withdraw their funds from the proposal when the buyout auction proposer is not `Migration.sol`.

In addition, it’s also possible that there are multiple ongoing proposals on the same vault and the buyout is started by one of them. To allow other proposals’ contributors to withdraw their fund, consider tracking the latest `proposalId` that started the buyout on a vault:

```solidity
mapping(address => uint256) public latestCommit;

function commit(address _vault, uint256 _proposalId) {
    ...
    if (currentPrice > proposal.targetPrice) {
        ...
        latestCommit[_vault] = _proposalId;
    }
}
```

For `leave`:

```solidity
(, address proposer, State current, , , ) = IBuyout(buyout).buyoutInfo(_vault);

// if buyout is started by this proposal, check that state is inactive. Else allow leaving.
if (proposer == address(this) && latestCommit[_vault] == _proposalId) {
    State required = State.INACTIVE;
    if (current != required) revert IBuyout.InvalidState(required, current);
}
```

For `withdrawContribution`:

```solidity
(, address proposer, State current, , , ) = IBuyout(buyout).buyoutInfo(_vault);

// if buyout is started by this proposal, check that state is inactive. Else allow withdrawing.
if (proposer == address(this) && latestCommit[_vault] == _proposalId) {
    State required = State.INACTIVE;
    if (current != required) revert IBuyout.InvalidState(required, current);
}
if (
    migrationInfo[_vault][_proposalId].newVault != address(0)
) revert NoContributionToWithdraw();
```

Starting a buyout can cause migration funds to become stuck in the contract. Agree this is High risk.

Selecting this submission as the primary for including POC code and including clear recs.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the interaction between the migration module and the buyout auction module in a vault‑based fractional ownership system. Migration proposals allow contributors to deposit funds that can later be withdrawn by invoking functions such as leave or withdrawContribution, but these functions first verify that the buyout auction associated with the same vault is in the INACTIVE state. The check does not consider whether the active buyout was triggered by the migration contract itself. Consequently, if an external participant starts a buyout while a migration proposal is still pending, the buyout state becomes ACTIVE and the migration functions reject any caller with an InvalidState error, even though the buyout was not initiated by the migration proposal. As a result, contributors who have already sent ether to the proposal find themselves unable to leave the proposal or retrieve their contributions. If the buyout later succeeds, the funds become permanently locked in the contract because the only path to withdraw is gated by a state that will never return to INACTIVE for that vault. The issue is discovered during an audit through unit tests that simulate a user (Bob) creating a migration proposal, contributing 0.5 ETH, and then another user (Alice) starting and completing a buyout, after which Bob’s attempts to leave or withdraw are consistently reverted. This bug is subtle because the contract’s logic correctly enforces the INACTIVE requirement for normal operation, giving the impression that any active buyout should block migration actions; however, it fails to account for the case where the buyout is unrelated to the migration proposal. The impact is that users lose access to their deposited funds, leading to apparent “funds disappear” or “refund missing” symptoms on the UI, where the balance shows a reduction but the withdrawal button is disabled and transactions revert. The affected parties include any contributor to a migration proposal, the protocol’s liquidity pool, and potentially the overall trustworthiness of the system. To remediate, the contract should differentiate between a buyout started by the migration contract and one started by an external auctioneer, either by checking the proposer address or by tracking the proposal identifier that triggered the buyout. By allowing withdrawals when the buyout proposer is not the migration contract, contributors can safely retrieve their funds regardless of concurrent auction activity, thereby restoring the intended accounting guarantees and preventing permanent fund lock‑up.

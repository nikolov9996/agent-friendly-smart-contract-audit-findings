---
id: 3551
severity: "High"
---

# Tokens can get stuck during migration if the L2 side fails leading to loss of funds

## Description

```solidity
function recieveL1Beans(address reciever, uint256 amount) external nonReentrant {
    require(
        msg.sender == address(BRIDGE) &&
        IL2Messenger(BRIDGE).xDomainMessageSender() == L1BEANSTALK
    );
    s.sys.migration.migratedL1Beans += amount;
    require(
        EXTERNALL1BEANS >= s.sys.migration.migratedL1Beans,
        "L2Migration: exceeds maximum migrated"
    );
    C.bean().mint(reciever, amount);
}
```
During the mirgration process between BeanL1ReceiverFacet and BeanL2MigrationFacet, when transactions fail on the L2 side, tokens are forever burnt with no existing method to reclaw them.

The migration process involves two key contracts: BeanL1ReceiverFacet and BeanL2MigrationFacet. The process starts on L1 where tokens are burned, and a message is sent to L2 to mint the equivalent amount of tokens.

Steps Involved:
Burning on L1: The BeanL2MigrationFacet contract burns the tokens from the user's L1 balance.
Message to L2: The contract then sends a message to L2 using the IL2Bridge interface, instructing the L2 contract to mint the equivalent amount of tokens.

Vulnerable Scenario:
If the message sent from L1 to L2 fails to execute successfully on L2 (e.g., due to contract limitations or gas issues), the tokens will have already been burned on L1, but the user will not receive the corresponding tokens on L2.
Specifically, the recieveL1Beans function on L2 could revert due to various reasons such as exceeding the maximum migrated beans or other contract-specific checks.

```solidity
function migrateL2Beans(
    address reciever,
    address L2Beanstalk,
    uint256 amount,
    uint32 gasLimit
) external nonReentrant {
    C.bean().burnFrom(msg.sender, amount);

    IL2Bridge(BRIDGE).sendMessage(
        L2Beanstalk,
        abi.encodeCall(IBeanL1RecieverFacet(L2Beanstalk).recieveL1Beans, (reciever, amount)),
        gasLimit
    );
}
```
If a migration request causes the total migrated beans to exceed this limit, the recieveL1Beans function will revert with the error "L2Migration: exceeds maximum migrated". Additionally, if the specified gas limit (gasLimit) is too low, the transaction might run out of gas during execution on L2.

Users will permanently lose their tokens as they are burned on L1 but not minted on L2.

## Proof of Concept

no poc

## Recommendation

```solidity
function recieveL1Beans(address reciever, uint256 amount) external nonReentrant {
    require(
        msg.sender == address(BRIDGE) &&
        IL2Messenger(BRIDGE).xDomainMessageSender() == L1BEANSTALK
    );
    s.sys.migration.migratedL1Beans += amount;
    require(
        EXTERNALL1BEANS >= s.sys.migration.migratedL1Beans,
        "L2Migration: exceeds maximum migrated"
    );
    C.bean().mint(reciever, amount);

    // Mark the migration as completed on L1
    bytes32 requestId = keccak256(abi.encodePacked(reciever, amount, block.timestamp));
    IL2Bridge(BRIDGE).sendMessage(
        L1Beanstalk,
        abi.encodeCall(BeanL2MigrationFacet(L1Beanstalk).markMigrationCompleted, (requestId)),
        gasLimit
    );
}
```
It is recommended to comprise a refund/reclaw mechanism for failed transactions on L2, so that tokens can be retrieved.

By implementing a retry mechanism and tracking migration requests, the potential issue of tokens getting stuck during the L1 to L2 migration can be mitigated. This approach ensures that users do not lose their tokens even if there are issues during the migration process.

```solidity
mapping(bytes32 => MigrationRequest) public migrationRequests;

struct MigrationRequest {
    address reciever;
    uint256 amount;
    uint256 timestamp;
    bool completed;
}

function migrateL2Beans(
    address reciever,
    address L2Beanstalk,
    uint256 amount,
    uint32 gasLimit
) external nonReentrant {
    C.bean().burnFrom(msg.sender, amount);

    bytes32 requestId = keccak256(abi.encodePacked(reciever, amount, block.timestamp));
    migrationRequests[requestId] = MigrationRequest(reciever, amount, block.timestamp, false);

    IL2Bridge(BRIDGE).sendMessage(
        L2Beanstalk,
        abi.encodeCall(IBeanL1RecieverFacet(L2Beanstalk).recieveL1Beans, (reciever, amount)),
        gasLimit
    );
}

function refundFailedMigration(bytes32 requestId) external {
    MigrationRequest storage request = migrationRequests[requestId];
    require(!request.completed, "Migration already completed");
    require(block.timestamp > request.timestamp + 1 days, "Migration still in process");

    C.bean().mint(request.reciever, request.amount);
    request.completed = true;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a loss‑of‑funds condition that occurs during the cross‑chain migration of Bean tokens from Layer 1 (L1) to Layer 2 (L2). The migration contract burns the user’s tokens on L1, then sends an asynchronous message to an L2 contract that is supposed to mint the same amount for the user. Because the burn and the mint are not performed atomically, the protocol relies on the external message succeeding. If the L2 call reverts – for example because the cumulative migrated amount would exceed a hard‑coded limit, because the supplied gas limit is insufficient, or because of any other contract‑specific check – the L2 mint never happens while the L1 tokens have already been destroyed. From the user’s perspective the balance on L1 becomes zero and the transaction receipt shows success, yet no tokens appear on L2, leading to the impression that the funds have simply disappeared. The issue was identified during a manual audit that examined the migration flow and noticed that there is no rollback or refund mechanism for failed L2 executions. It is difficult to detect because the L1 burn emits a normal event and the failure occurs on a different chain, so the user interface on L1 shows no error. The root cause is the lack of a two‑phase commit or escrow pattern that would guarantee either both sides succeed or both revert, combined with missing tracking of pending migration requests. The impact is permanent loss of tokens for any user whose migration triggers a revert, which can be induced deliberately by sending a request that exceeds the migration cap or by providing an intentionally low gas limit. To remediate, the protocol should record each migration request, allow a timeout‑based refund or retry, and only mark the migration as completed after the L2 mint succeeds. This transforms the bridge from a non‑atomic burn‑then‑mint design into a safe cross‑chain transfer that preserves accounting invariants and prevents funds from being irretrievably burnt.

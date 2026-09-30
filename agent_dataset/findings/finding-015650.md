---
id: 15650
severity: "High"
---

# Workers could withdraw without deregister and waiting for the lock period

## Description

The designed flow and expected worker's behavior for withdrawing their bond is to first deregister the registered peerId. After that, they have to wait for the lock period before they can trigger the withdraw, as it can be seen from withdraw functions expected flow.

```solidity
* @dev Withdraws the bond of a worker.
* @param peerId The unique peer ID of the worker.
* @notice Worker must be inactive
* @notice Worker must be registered by the caller
* @notice Worker must be deregistered for at least lockPeriod // @audit - prerequisite for withdraw
function withdraw(bytes calldata peerId) external whenNotPaused {
    uint256 workerId = workerIds[peerId];
    require(workerId != 0, "Worker not registered");
    Worker storage worker = workers[workerId];
    require(!isWorkerActive(worker), "Worker is active");
    require(worker.creator == msg.sender, "Not worker creator");
    require(block.number >= worker.deregisteredAt + lockPeriod(), "Worker is locked");
    uint256 bond = worker.bond;
    delete workers[workerId];
    tSQD.transfer(msg.sender, bond);
    emit WorkerWithdrawn(workerId, msg.sender);
}
```

However, as long as the worker is not yet active (the current block has not yet reached the registeredAt), it can directly withdraw without calling deregister and waiting for the lock period. While this does not impact the TVL calculation, it violates the designed withdrawal flow and does not remove the worker from the activeWorkerIds array which will enable the unbounded loop attack vector.

Added POC to WorkerRegistration.withdraw.t.sol.

```solidity
function testImmediatelyWithdraw() public {
    vm.roll(176329477);
    workerRegistration.register(workerId);
    workerRegistration.withdraw(workerId);
}
```

## Proof of Concept

No poc.

## Recommendation

Consider to add extra check when withdraw is performed:

```solidity
function withdraw(bytes calldata peerId) external whenNotPaused {
    uint256 workerId = workerIds[peerId];
    require(workerId != 0, "Worker not registered");
    Worker storage worker = workers[workerId];
    require(!isWorkerActive(worker), "Worker is active");
    require(worker.creator == msg.sender, "Not worker creator");
    require(block.number >= worker.deregisteredAt + lockPeriod() && worker.deregisteredAt != 0, "Worker is locked");
    uint256 bond = worker.bond;
    delete workers[workerId];
    tSQD.transfer(msg.sender, bond);
    emit WorkerWithdrawn(workerId, msg.sender);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the withdrawal mechanism for bonded workers in a staking‑like system. The intended design requires a worker to first deregister its unique identifier and then wait for a predefined lock period before being allowed to pull out the bonded tokens. This sequence enforces a clear lifecycle: registration → activation → deregistration → lock period → withdrawal. The contract, however, omits a critical condition that checks whether the worker has actually been deregistered before allowing the withdrawal. As a result, if a worker has been registered but has not yet become active – meaning the current block number is still earlier than the activation block – the contract permits an immediate withdrawal of the bond without any deregistration call and without respecting the lock period. The root cause is the missing validation of the deregistration timestamp (or a flag indicating that deregistration has occurred) in the withdraw function. Because the check only verifies that the worker is inactive and that the lock period has elapsed relative to a possibly zero deregistration timestamp, the condition is trivially satisfied for inactive, never‑activated workers. An attacker can exploit this by registering a worker, waiting zero blocks, and then calling withdraw directly, receiving the bond instantly. While the total value locked (TVL) calculation remains correct, the worker’s entry is not removed from the activeWorkerIds array, leaving a stale reference. This stale entry can be iterated over in functions that assume every element in the array corresponds to a valid worker, opening the possibility of an unbounded loop or denial‑of‑service attack when the array grows unchecked. The issue was discovered during a manual audit that compared the documented withdrawal flow with the actual implementation and verified the behavior with a test that called withdraw immediately after registration. The bug is subtle because the contract still enforces inactivity and a lock‑period check, which can give a false sense of safety, and the premature withdrawal does not affect obvious accounting numbers, making it easy to overlook. To remediate, the withdraw routine should include an explicit requirement that the worker has been deregistered (e.g., deregisteredAt != 0) and that the current block number is at least the deregistration block plus the lock period. This restores the intended lifecycle and ensures that the worker is also removed from any active‑worker collections, preventing the unbounded‑loop vector. From a user perspective, a worker expecting to wait for the lock period may instead receive the bond instantly, but the system’s internal worker list will still show the worker as active, leading to confusion and potential failures in later operations that iterate over that list. The flaw represents a class of state‑transition validation errors where a contract fails to enforce prerequisite state changes before allowing a privileged action, breaking business logic and opening attack surfaces such as denial‑of‑service or inconsistent state.

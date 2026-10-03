---
id: 25286
severity: "Low/Info"
---

# MToken's total principal invariant doesn't hold without MinterGateway, leading to potential principal loss

## Description

In function [MToken._mint](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L217-L233>), when the account is an earner, the principal gets added to both its raw balance and to the global variable principalOfTotalEarningSupply.

However, this addition is unchecked, allowing the total principle to silently overflow the maximum uint112 amount. The final check assessing whether or not the total principal (earning and non earning supply) is greater than type(uint112).max will pass if the earning principal amount already overflowed before in _addEarningAmount.

This can further cause damage to earners if e.g. Alice is able to overflow Bob's balance:

1. Bob is going to call stopEarning.
2. Alice frontruns Bob's transaction and transfers him the exact principal amount to make Bob's balance equal type(uint112).max + 2.
3. When Bob calls stopEarning, there's an unsafe cast which will truncate his entire balance: uint112 principalAmount_ = uint112(_balances[account_].rawBalance);. Bob's new balance will be 1. It should be noted that the MinterGateway [prevents the invariant from easily breaking](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L266-L271>). But such an important MToken invariant should not be solely preserved by an external contract, as it can lead to potential problems in the future (e.g. changing the MinterGateway contract).

## Proof of Concept

No PoC provided.

## Recommendation

Consider removing the unchecked addition of principalOfTotalEarningSupply in _addEarningAmount:

```solidity
function _addEarningAmount(address account_, uint112 principalAmount_)
internal {
    unchecked {
        _balances[account_].rawBalance += principalAmount_;
    }
    principalOfTotalEarningSupply += principalAmount_;
}
```

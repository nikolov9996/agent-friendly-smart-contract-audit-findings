---
id: 25454
severity: "Low/Info"
---

# Pausable or Blacklist tokens may cause liquidations to fail

## Description



## Proof of Concept

## Vulnerability Detail

Liquidations in Nerite [push](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/TroveManager.sol#L460>) collateral tokens to the `msg.sender`, from the Active Pool and [to](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/TroveManager.sol#L433>) the StabilityPool.

If any of those 3 addresses is blacklisted or the collateral token is paused, liquidations that would normally work, can be DOSsed.

## Impact

DoSed liquidations due to blacklisted addresses or paused tokens.

## Code Snippet

[XVS](<https://arbiscan.io/address/0xc1Eb7689147C81aC840d4FF0D298489fc7986d52>) [tETH](<https://arbiscan.io/address/0xd09acb80c1e8f2291862c4978a008791c9167003>)

For example, for XVS, it is a standard OZ ERC20 with the following alteration to `_beforeTokenTransfer`:

```solidity
    /**
     * @notice Hook that is called before any transfer of tokens. This includes
     * minting and burning.
     * @param from_ Address of account from which tokens are to be transferred.
     * @param to_ Address of the account to which tokens are to be transferred.
     * @param amount_ The amount of tokens to be transferred.
     * @custom:error AccountBlacklisted is thrown when either `from` or `to` address is blacklisted.
     */
    function _beforeTokenTransfer(address from_, address to_, uint256 amount_) internal override whenNotPaused {
        if (_blacklist[to_]) {
            revert AccountBlacklisted(to_);
        }
        if (_blacklist[from_]) {
            revert AccountBlacklisted(from_);
        }
    }
```

## Recommendation

These risks are not really possible to completely mitigate, unless other tokens are used.

---
id: 25654
severity: "Low/Info"
---

# SuperToken._skipSelfMint silently skips minting, breaking custom SuperToken implementations

## Description



## Proof of Concept

## Vulnerability Detail

The `_skipSelfMint` flag is used internally to prevent a mint/burn loop when withdrawing ETH from the yield backend. When set to `true`, `selfMint()` silently returns without minting any tokens:

```solidity
function selfMint(
    address account,
    uint256 amount,
    bytes memory userData
)
    external virtual override
    onlySelf
{
    if (!_skipSelfMint) {
        // ... actual minting logic ...
    }
}
```

The problem is that contracts extending SuperToken (e.g., custom wrapper contracts) may implement a `receive()` function that calls `selfMint()` expecting tokens to be minted. If `_skipSelfMint` is set, the call succeeds but no tokens are minted, and the accounting gets corrupted.

For example, a custom SuperToken with fee logic:

```solidity
receive() external payable {
    uint256 fees = msg.value * 1 / 10000; // 1 BPS fee
    uint256 amount = msg.value - fees;
    this.selfMint(msg.sender, amount, "");
    totalFees += fees;
}
```

When `_skipSelfMint` is true, this code collects fees but mints nothing, causing users to lose funds.

## Impact

Custom SuperToken implementations that have other logic in their `receive()` function, such as the example above, will become broken. The current [SETH](<https://github.com/superfluid-finance/protocol-monorepo/blob/dev/packages/ethereum-contracts/contracts/tokens/SETH.sol>) already has this problem, since it emits the event `emit TokenUpgraded(msg.sender, msg.value);` on `receive()`, but no tokens are actually minted.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/SuperToken.sol#L765-L781](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/SuperToken.sol#L765-L781>)

```solidity
function selfMint(
    address account,
    uint256 amount,
    bytes memory userData
)
    external virtual override
    onlySelf
{
    if (!_skipSelfMint) {
        if (address(_yieldBackend) != address(0)) {
            delegateCallChecked(address(_yieldBackend), abi.encodeCall(IYieldBackend.deposit, (amount)));
        }

        _mint(msg.sender, account, amount, userData.length != 0 /* invokeHook */,
            userData.length != 0 /* requireReceptionAck */, userData, new bytes(0));
    }
}
```

## Recommendation

Should be flagged to any SuperToken implementation, so it makes sure when the skipSelfMint flag is true, all logic in the receive function should be skipped, not just selfMint().

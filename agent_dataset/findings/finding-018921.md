---
id: 18921
severity: "Medium"
---

# `TokenManager`’s flow limit logic is broken for `ERC777` tokens

## Description

`TokenManager` implementations inherit from the `FlowLimit` contract that keeps track of flow in and flow out. If these two values are too far away from each other, it reverts:
```solidity
function _addFlow(
    uint256 flowLimit,
    uint256 slotToAdd,
    uint256 slotToCompare,
    uint256 flowAmount
) internal {
    uint256 flowToAdd;
    uint256 flowToCompare;
    assembly {
        flowToAdd := sload(slotToAdd)
        flowToCompare := sload(slotToCompare)
    }
    if (flowToAdd + flowAmount > flowToCompare + flowLimit) revert FlowLimitExceeded();
    assembly {
        sstore(slotToAdd, add(flowToAdd, flowAmount))
    }
}
```

Flow in and flow out are increased when some tokens are transferred from one blockchain to another. There are 3 different kinds of `TokenMaganer`:

  * Lock/Unlock
  * Mint/Burn
  * Liquidity Pool

Let’s see how Lock/Unlock and Liquidity Pool implementations handle cases when they have to transfer tokens to users:
```solidity
function _giveToken(address to, uint256 amount) internal override returns (uint256) {
    IERC20 token = IERC20(tokenAddress());
    uint256 balance = IERC20(token).balanceOf(to);

    SafeTokenTransfer.safeTransfer(token, to, amount);

    return IERC20(token).balanceOf(to) - balance;
}

function _giveToken(address to, uint256 amount) internal override returns (uint256) {
    IERC20 token = IERC20(tokenAddress());
    uint256 balance = IERC20(token).balanceOf(to);

    SafeTokenTransferFrom.safeTransferFrom(token, liquidityPool(), to, amount);

    return IERC20(token).balanceOf(to) - balance;
}
```

As can be seen, they return a value equal to a balance difference before and after token transfer. This returned value is subsequently used by the `giveToken` function in order to call `_addFlowIn`:
```solidity
function giveToken(address destinationAddress, uint256 amount) external onlyService returns (uint256) {
    amount = _giveToken(destinationAddress, amount);
    _addFlowIn(amount);
    return amount;
}
```

The problem arises when `token` is `ERC777` token. In that case, the token receiver can manipulate its balance in order to increase flow in more than it should be; see POC section for more details.

There is no mechanism that will disallow someone from creating `TokenManager` with `ERC777` token as an underlying token, so it’s definitely a possible scenario and the protocol would malfunction if it happens.

Note that it’s not an issue like “users may deploy `TokenManager` for their malicious tokens that could even lie about `balanceOf`”. Users may simply want to deploy `TokenManager` for some `ERC777` token and bridge their `ERC777` tokens and there is nothing unusual about it.

It is possible to manipulate flow in when there is `TokenManager` of type Lock/Unlock or Liquidity Pool and the underlying token is `ERC777` token. It could be used to create DoS attacks, as it won’t be possible to transfer tokens from one blockchain to another when the flow limit is reached (it may be possible to send them from one blockchain, but it will be impossible to receive them on another one due to the `revert` in the `_addFlow` function).

In order to recover, `flowLimit` could be set to `0`, but the feature was introduced in order to control flow in and flow out. Setting `flowLimit` to `0` means that the protocol won’t be able to control it anymore.

Here, the availability of the protocol is impacted, but an extra requirement is that there has to be `TokenManager` of Lock/Unlock or Liquidity Pool kind with `ERC777` underlying token, so I’m submitting this issue as Medium.

## Proof of Concept

Consider the following scenario:

  1. `TokenManager` of type Lock/Unlock was deployed on blockchain `X` with underlying `ERC777` token (like FLUX, for example). Let’s call this token `T`.
  2. Assume that blockchain `X` has low gas price (not strictly necessary, but will be helpful to visualize the issue).
  3. Alice wants to move their tokens (`T`) from blockchain `Y` to `X`, so they call `sendToken` from `TokenManagerLockUnlock` in order to start the process.
  4. Bob sees that and they also call `sendToken`, but with some dust amount of token `T`, they schedules that transaction from their smart contract called `MaliciousContract`.
  5. Bob’s transaction is handled first and finally `TokenManagerLockUnlock::_giveToken` is called in order to give that dust amount of `T` to Bob’s contract (`MaliciousContract`).
  6. `_giveToken`:
```solidity
function _giveToken(address to, uint256 amount) internal override returns (uint256) {
    IERC20 token = IERC20(tokenAddress());
    uint256 balance = IERC20(token).balanceOf(to);

    SafeTokenTransfer.safeTransfer(token, to, amount);

    return IERC20(token).balanceOf(to) - balance;
}
```
First, this records current balance of `T` of `MaliciousContract`, which happens to be `0` and calls `transfer`, which finally calls `MaliciousContract::tokensReceived` hook.

  7. `MaliciousContract::tokensReceived` hook looks as follows:
```solidity
function tokensReceived(
    address operator,
    address from,
    address to,
    uint256 amount,
    bytes calldata data,
    bytes calldata operatorData
) external
{
    if (msg.sender == <TOKEN_MANAGER_ADDRESS>)
        maliciousContractHelper.sendMeT();
    else
        return;
}
```
Where `<TOKEN_MANAGER_ADDRESS>` is the address of the relevant `TokenManager` and `maliciousContractHelper` is an instance of `MaliciousContractHelper`. That exposes the `sendMeT` function, which will send all tokens that it has to the `MaliciousContract` instance that called it.

  8. `maliciousContractHelper` has a lot of tokens `T`, so when `tokensReceived` returns, `T.balanceOf(MaliciousContract)` will increase a lot despite the fact that only a dust amount of `T` was sent from `TokenManager`.
  9. The execution will return to `_giveToken` and returned value will be huge, since `IERC20(token).balanceOf(to) - balance` will now be a big value, despite the fact that `amount` was close to `0`.
  10. Flow in amount will increase a lot, so that `flowLimit` is reached and Alice’s transaction will not be processed.

In short, Bob has increased the flow in amount for `TokenManager` by sending to their contract a lot of money in `ERC777` `tokensReceived` hook from their other contract. It didn’t cost them much since they sent only a tiny amount of `T` between blockchains. Hence they could use almost all of their `T` tokens for the attack.

Of course Bob could perform this attack without waiting for Alice to submit their transaction. The scenario presented above was just an example. In reality, Bob can do this at any moment.

It also seems possible to transfer tokens from the same blockchain to itself (by specifying wrong `destinationChain` in `sendToken` or just by specifying `destinationChain = <CURRENT_CHAIN>`), so Bob can have their tokens `T` only on one blockchain.

If gas price on that blockchain is low, Bob can perform that attack a lot of times. All they need to do is to send tokens back to `MaliciousContractHelper` after each attack (so that it can send it to `MaliciousContract` as described above). Finally, they will reach `flowLimit` for `TokenManager` and will cause denial of service.

## Recommendation

I would recommend doing one of the following:

  * Acknowledge the issue and warn users that the protocol doesn’t support `ERC777` tokens (possibly even check and if `TokenManager` with `ERC777` underlying token is to be deployed - just revert)
  * Correct the value returned by `_giveTokens` to ensure that it doesn’t exceed `amount`, as follows:

```solidity
uint currentBalance = IERC20(token).balanceOf(to);
if (currentBalance - balance > amount)
    return amount;
return currentBalance - balance;
```

Fixed so that the amount returned can never be higher than the initial amount.

Public PR link: <https://github.com/axelarnetwork/interchain-token-service/pull/102>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way TokenManager contracts calculate the amount of tokens that have been transferred into the bridge (flow‑in). Both the Lock/Unlock and Liquidity‑Pool implementations call an internal _giveToken function that records the recipient’s token balance before the transfer, performs a safeTransfer, then returns the difference between the post‑transfer balance and the pre‑transfer balance. This returned value is subsequently fed to the _addFlowIn routine, which checks that the cumulative flow‑in does not exceed a configured flowLimit. The logic assumes that the balance difference is exactly equal to the amount that was sent. However, ERC777 tokens introduce a tokensReceived hook that is executed after the transfer. A malicious contract can implement this hook to pull additional ERC777 tokens from any source it controls, thereby inflating its own balance after the transfer completes. Because the balance difference is measured after the hook has run, the _giveToken function can return a value far larger than the original amount parameter. When this inflated value is added to the flow‑in counter, the flowLimit can be reached or exceeded much earlier than intended, causing subsequent legitimate bridge transfers to revert with the FlowLimitExceeded error. The impact is a denial‑of‑service condition: users attempting to move tokens across chains receive a revert, their expected tokens never appear on the destination chain, and the protocol’s availability is degraded. The bug manifests only when a TokenManager of type Lock/Unlock or Liquidity‑Pool is instantiated with an ERC777 token as the underlying asset; the protocol does not currently prevent such deployments, making the scenario realistic. From a user’s perspective the symptoms are a transaction that appears to succeed on the sending side but fails on the receiving side, often with an unexpected “flow limit exceeded” revert, and the user sees no tokens arriving despite having sent them. The root cause is an accounting flaw that trusts a balance‑difference measurement without accounting for token callbacks that can modify balances after the transfer. This class of bug can be described as an “inflated accounting due to token hook manipulation”. It is hard to notice because ERC777 complies with the ERC20 interface and the balance‑difference appears correct for standard ERC20 tokens, so the extra increase is only observable when the hook is triggered. The recommended mitigation is either to forbid ERC777 tokens entirely (by detecting the interface and reverting on deployment) or to cap the value returned by _giveToken so that it never exceeds the amount argument, thereby ensuring that flow‑in is calculated based on the intended transfer amount rather than the potentially manipulated post‑transfer balance. Implementing such a check restores the intended flow‑limit guarantees without sacrificing support for standard ERC20 tokens.

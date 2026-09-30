---
id: 22864
severity: "High"
---

# Submitting mint request using user's trading

## Description

The Elfi protocol provides a feature that allows users to transfer a portion of their tokens after depositing them into a trading account, helping them manage their When the keeper fails to execute the execute method, it will call the corresponding cancel method to revoke this request The problem arises if the mint request uses the trading balance to get elfi tokens. This is the logic where users can use trading account balances to obtain elfi tokens.
```solidity
function _mintStakeToken(Mint.Request memory mintRequest) internal returns (uint256 stakeAmount) {
    -- SNIP --
    if (mintRequest.requestTokenAmount > mintRequest.walletRequestTokenAmount) {
        _transferFromAccount(
            mintRequest.account,
            mintRequest.requestToken,
            mintRequest.requestTokenAmount - mintRequest.walletRequestTokenAmount
        );
    }
    -- SNIP --
}
```
The MintProcess::cancelMintStakeToken refunds the tokens sent from user EOA to the vault. However, the trading balance account isn't refunded if mint requests are executed and funded by the trading account.
```solidity
function cancelMintStakeToken(uint256 requestId, Mint.Request memory mintRequest, bytes32 reasonCode) external {
    implementation for trading account

    VaultProcess.transferOut(
        mintRequest.isCollateral
            ? IVault(address(this)).getPortfolioVaultAddress() // ok
            : IVault(address(this)).getLpVaultAddress(),// ok
        mintRequest.requestToken,
        mintRequest.account, //transfer to user
        mintRequest.walletRequestTokenAmount
    );
    Mint.remove(requestId);
    emit CancelMintEvent(requestId, mintRequest, reasonCode);
}
```
Users who staked with trading balance will lose tokens if mint requests are cancelled.

## Proof of Concept

no poc

## Recommendation

(Externally Owned Account) or to the trading account. The following solution, updates the trading balance account:
```solidity
function cancelMintStakeToken(uint256 requestId, Mint.Request memory mintRequest, bytes32 reasonCode) external {
    if (mintRequest.requestTokenAmount > mintRequest.walletRequestTokenAmount) {
        Account.Props storage accountProps = Account.load(mintRequest.account);
        accountProps.checkExists();
        accountProps.addToken(mintRequest.requstToken, mintrequest.requestTokenAmount);
    }

    implementation for trading account

    VaultProcess.transferOut(
        mintRequest.isCollateral
            ? IVault(address(this)).getPortfolioVaultAddress() // ok
            : IVault(address(this)).getLpVaultAddress(),// ok
        mintRequest.requestToken,
        mintRequest.account, //transfer to user
        mintRequest.walletRequestTokenAmount
    );
    Mint.remove(requestId);
    emit CancelMintEvent(requestId, mintRequest, reasonCode);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the handling of mint requests that draw tokens from a user’s trading account balance in the Elfi protocol. When a mint request is created, the contract may transfer a portion of the required tokens directly from the user’s trading account if the amount requested exceeds the amount supplied from the user’s external owned account (EOA). The internal function _mintStakeToken performs this transfer by calling _transferFromAccount for the excess amount. However, if the keeper that is supposed to execute the mint request fails and the request is later cancelled via cancelMintStakeToken, the cancellation routine only refunds the tokens that were originally sent from the EOA (mintRequest.walletRequestTokenAmount). The portion that was taken from the trading balance (mintRequest.requestTokenAmount‑mintRequest.walletRequestTokenAmount) is never returned to the user’s trading account. As a result, users who relied on their trading balance to fund a mint lose that portion of tokens permanently. The root cause is an incomplete refund logic in the cancelMintStakeToken function: it does not credit back the trading‑account portion, nor does it update the internal accounting structures for the trading account. Exploitation is straightforward – any user can submit a mint request that uses the trading balance, then trigger or wait for a cancellation (for example by causing the keeper to miss the execution window). When the request is cancelled, the protocol refunds only the EOA portion, leaving the trading balance reduced, which appears to the user as missing funds. The impact is a loss of user assets and a breach of the protocol’s accounting guarantees, because the protocol’s internal token accounting no longer matches the actual token holdings. This condition occurs only when the request’s token amount is larger than the wallet‑provided amount, i.e., when the trading balance is used. The affected parties are the users who submit such mint requests and any downstream participants that rely on accurate token balances. The issue was discovered during a manual audit of the mint‑cancellation flow, where the auditor noticed that the refund logic omitted the trading‑account portion. It can be hard to notice because the UI typically shows a successful cancellation and may not display a warning about the missing portion; the user simply sees a lower balance after cancellation without an explicit error. The proper fix is to extend cancelMintStakeToken so that, when the request involved a trading‑account transfer, the contract restores the exact amount to the user’s trading account (for example by loading the account properties and calling addToken) before performing the existing vault transfer. This brings the refund behavior in line with the intended business logic that a cancelled mint should return all tokens that were taken, regardless of their source, and restores accounting consistency. The bug belongs to the class of partial‑transfer refund errors, where a function that handles multiple funding sources fails to reverse all of them on rollback, leading to asset loss and accounting inconsistency.

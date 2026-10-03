---
id: 25568
severity: "Medium"
---

# Potential ETH Loss Due to transfer Usage in Requestor Contract on zkSync

## Description



## Proof of Concept

## Vulnerability Detail

- Users (or bots) interact with [RngWitnet](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-rng-witnet/src/RngWitnet.sol#L132>) to request a random number and start a draw in the `DrawManager` contract. To generate a random number, users must provide some `ETH` that will be sent to [WitnetRandomness](<https://github.com/witnet/witnet-solidity-bridge/blob/6cf9211928c60e4d278cc70e2a7d5657f99dd060/contracts/apps/WitnetRandomnessV2.sol#L372>) to generate the random number.

```js
    function startDraw(uint256 rngPaymentAmount, DrawManager _drawManager, address _rewardRecipient) external payable returns (uint24) {
            (uint32 requestId,,) = requestRandomNumber(rngPaymentAmount);
            return _drawManager.startDraw(_rewardRecipient, requestId);
    }
```

- The `ETH` sent with the transaction may or may not be used (if there is already a request in the same block, it won't be used). Any remaining or unused `ETH` will be sent to [Requestor](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-rng-witnet/src/Requestor.sol#L36>), so the user can withdraw it later.
- The issue is that the `withdraw` function in the `Requestor` contract uses `transfer` to send `ETH` to the receiver. This may lead to users being unable to withdraw their funds .

```js
 function withdraw(address payable _to) external onlyCreator returns (uint256) {
        uint256 balance = address(this).balance;
 >>       _to.transfer(balance);
        return balance;
 }
```

- The protocol will be deployed on different chains including `zkSync`, on `zkSync` the use of `transfer` can lead to issues, as seen with [921 ETH Stuck in zkSync Era](<https://medium.com/coinmonks/gemstoneido-contract-stuck-with-921-eth-an-analysis-of-why-transfer-does-not-work-on-zksync-era-d5a01807227d>).since it has a fixed amount of gas `23000` which won't be anough in some cases even to send eth to an `EOA`, It is explicitly mentioned in their docs to not use the `transfer` method to send `ETH` [here](<https://docs.zksync.io/build/quick-start/best-practices.html#use-call-over-send-or-transfer>).

> notice that in case `msg.sender` is a contract that have some logic on it's receive or fallback function the `ETH` is definitely not retrievable. since this contract can only withdraw eth to it's [own addres](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-rng-witnet/src/RngWitnet.sol#L99-L102>) which will always revert.

## Impact

- Draw Bots' `ETH` may be irretrievable or undelivered, especially on zkSync, due to the use of `.transfer`.

## Code Snippet

- [https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-rng-witnet/src/Requestor.sol#L27-L30](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-rng-witnet/src/Requestor.sol#L27-L30>)

## Recommendation

- recommendation to use `.call()` for `ETH` transfer.

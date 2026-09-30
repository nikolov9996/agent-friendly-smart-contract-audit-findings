---
id: 19665
severity: "High"
---

# Incorrect amounts of ETH are transferred to the DAO treasury in `ERC20TokenEmitter::buyToken`

## Description

While users buying governance tokens with `ERC20TokenEmitter::buyToken` function, some portion of the provided ETH is reserved for creators according to the [`creatorRateBps`](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/ERC20TokenEmitter.sol#L42).

A part of this creator’s reserved ETH is directly sent to the creators according to [`entropyRateBps`](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/ERC20TokenEmitter.sol#L45), and the remaining part is used to buy governance tokens for creators.

That remaining part, which is used to buy governance tokens, is never sent to the DAO treasury. It is locked in the `ERC20Emitter` contract, causing value leaks for treasury in every `buyToken` function call.

```solidity
function buyToken(
    address[] calldata addresses,
    uint[] calldata basisPointSplits,
    ProtocolRewardAddresses calldata protocolRewardsRecipients
) public payable nonReentrant whenNotPaused returns (uint256 tokensSoldWad) {
    // ...

    // Get value left after protocol rewards
    uint256 msgValueRemaining = _handleRewardsAndGetValueToSend(
        msg.value,
        protocolRewardsRecipients.builder,
        protocolRewardsRecipients.purchaseReferral,
        protocolRewardsRecipients.deployer
    );

    //Share of purchase amount to send to treasury
    uint256 toPayTreasury = (msgValueRemaining * (10_000 - creatorRateBps)) / 10_000;

    //Share of purchase amount to reserve for creators
    //Ether directly sent to creators
    uint256 creatorDirectPayment = ((msgValueRemaining - toPayTreasury) * entropyRateBps) / 10_000;
    //Tokens to emit to creators
    int totalTokensForCreators = ((msgValueRemaining - toPayTreasury) - creatorDirectPayment) > 0
        ? getTokenQuoteForEther((msgValueRemaining - toPayTreasury) - creatorDirectPayment)
        : int(0);

    // Tokens to emit to buyers
    int totalTokensForBuyers = toPayTreasury > 0 ? getTokenQuoteForEther(toPayTreasury) : int(0);

    //Transfer ETH to treasury and update emitted
    emittedTokenWad += totalTokensForBuyers;
    if (totalTokensForCreators > 0) emittedTokenWad += totalTokensForCreators;

    //Deposit funds to treasury
    (bool success, ) = treasury.call{ value: toPayTreasury }(new bytes(0)); //@audit-issue Treasury is not paid correctly. Only the buyers share is sent. Creators share to buy governance tokens are not sent to treasury
    require(success, "Transfer failed.");                                   //@audit `creators total share` - `creatorDirectPayment` should also be sent to treasury. ==> Which is "((msgValueRemaining - toPayTreasury) - creatorDirectPayment)"

    //Transfer ETH to creators
    if (creatorDirectPayment > 0) {
        (success, ) = creatorsAddress.call{ value: creatorDirectPayment }(new bytes(0));
        require(success, "Transfer failed.");
    }

    // ... rest of the code
}
```

In the code above:

`toPayTreasury` is the buyer’s portion of the sent ether.  
`(msgValueRemaining - toPayTreasury)` is the creator’s portion of the sent ether.  
`((msgValueRemaining - toPayTreasury) - creatorDirectPayment)` is the remaining part of the creator’s share after direct payment _(which is used to buy the governance token)._

As we can see above, the part that is used to buy governance tokens is not sent to the treasury. Only the buyer’s portion is sent.

## Proof of Concept

**Coded PoC**

You can use the protocol’s own test suite to run this PoC.

-Copy and paste the snippet below into the `ERC20TokenEmitter.t.sol` test file.  
-Run it with `forge test --match-test testBuyToken_ValueLeak -vvv`
    
```solidity
function testBuyToken_ValueLeak() public {
        
    // Set creator and entropy rates.
    // Creator rate will be 10% and entropy rate will be 40%
    uint256 creatorRate = 1000;
    uint256 entropyRate = 5000;
    vm.startPrank(address(dao));
    erc20TokenEmitter.setCreatorRateBps(creatorRate);
    erc20TokenEmitter.setEntropyRateBps(entropyRate);

    // Check dao treasury and erc20TokenEmitter balances. Balance of both of them should be 0.
    uint256 treasuryETHBalance_BeforePurchase = address(erc20TokenEmitter.treasury()).balance;
    uint256 emitterContractETHBalance_BeforePurchase = address(erc20TokenEmitter).balance;
    
    assertEq(treasuryETHBalance_BeforePurchase, 0);
    assertEq(emitterContractETHBalance_BeforePurchase, 0);

    // Create token purchase parameters
    address[] memory recipients = new address[](1);
    recipients[0] = address(1);
    uint256[] memory bps = new uint256[](1);
    bps[0] = 10_000;

    // Give some ETH to user and buy governance token.
    vm.startPrank(address(0));
    vm.deal(address(0), 100000 ether);

    erc20TokenEmitter.buyToken{ value: 100 ether }(
        recipients,
        bps,
        IERC20TokenEmitter.ProtocolRewardAddresses({
            builder: address(0),
            purchaseReferral: address(0),
            deployer: address(0)
        })
    );

    // User bought 100 ether worth of tokens.
    // Normally with 2.5% fixed protocol rewards, 10% creator share and 50% entropy share: 
    //  ->  2.5 ether is protocol rewards.
    //  ->  87.75 ether is buyer share (90% of the 97.5)
    //  ->  9.75 of the ether is creators share
    //          - 4.875 ether directly sent to creators
    //          - 4.875 ether should be used to buy governance token and should be sent to the treasury.
    // However, the 4.875 ether is never sent to the treasury even though it is used to buy governance tokens. It is stuck in the Emitter contract. 

    // Check balances after purchase.
    uint256 treasuryETHBalance_AfterPurchase = address(erc20TokenEmitter.treasury()).balance;
    uint256 emitterContractETHBalance_AfterPurchase = address(erc20TokenEmitter).balance;
    uint256 creatorETHBalance_AfterPurchase = address(erc20TokenEmitter.creatorsAddress()).balance;

    // Creator direct payment amount is 4.875 as expected
    assertEq(creatorETHBalance_AfterPurchase, 4.875 ether);
    
    // Dao treasury has 87.75 ether instead of 92.625 ether. 
    // 4.875 ether that is used to buy governance tokens for creators is never sent to treasury and still in the emitter contract.
    assertEq(treasuryETHBalance_AfterPurchase, 87.75 ether);
    assertEq(emitterContractETHBalance_AfterPurchase, 4.875 ether);
}
```

Results after running the test:
    
```
Running 1 test for test/token-emitter/ERC20TokenEmitter.t.sol:ERC20TokenEmitterTest
[PASS] testBuyToken_ValueLeak() (gas: 459490)
Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 11.25ms
     
Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

I would recommend transferring the remaining ETH used to buy governance tokens to the treasury.
    
```solidity
    uint256 creatorsEthAfterDirectPayment = ((msgValueRemaining - toPayTreasury) - creatorDirectPayment);
    
    //Deposit funds to treasury
    (bool success, ) = treasury.call{ value: toPayTreasury + creatorsEthAfterDirectPayment }(new bytes(0));
    require(success, "Transfer failed.");
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the ERC20TokenEmitter contract’s buyToken function, where the ETH allocated for creators is split into a direct payment and a portion intended to purchase governance tokens. While the direct payment is correctly forwarded to the creators address, the remaining creator share – the amount that should be used to mint governance tokens – is never transferred to the DAO treasury. Instead, this ETH stays locked inside the ERC20TokenEmitter contract. The root cause is an omission in the transfer logic: only the buyer’s share (toPayTreasury) is sent to the treasury, and the creators’ token‑purchase share (creatorsEthAfterDirectPayment) is omitted from the call to treasury.call. An attacker does not need to perform any special steps; any call to buyToken with non‑zero creatorRateBps and entropyRateBps automatically triggers the leak, because the function calculates a creator portion, sends the direct payment, but fails to move the residual ETH to the treasury. The impact is a systematic reduction of treasury funds – each token purchase leaves a chunk of ETH stranded in the emitter contract, decreasing the protocol’s available capital and breaking the accounting assumption that all ETH used to mint governance tokens ends up in the treasury. From a user’s perspective, the symptoms are that after a purchase the DAO treasury balance is lower than expected while the emitter contract holds a non‑zero ETH balance; buyers receive the correct amount of tokens, creators receive their direct payment, but the protocol’s accounting shows missing funds. The issue was discovered during a security audit and confirmed with a unit test that measured balances before and after a purchase, revealing the value leak. It can be hard to notice because the contract still holds the ETH, so no explicit loss is visible on the external transaction trace, and the token minting proceeds normally. The bug belongs to the class of “incorrect fund allocation” or “partial transfer omission” bugs, where a calculated share of value is never forwarded to its intended recipient. To remediate, the transfer to the treasury should be amended to include both the buyer’s share and the creators’ token‑purchase share, i.e., treasury.call{value: toPayTreasury + creatorsEthAfterDirectPayment}(). This ensures that all ETH used for token issuance is accounted for in the treasury, restoring the intended financial flow and eliminating the leak.

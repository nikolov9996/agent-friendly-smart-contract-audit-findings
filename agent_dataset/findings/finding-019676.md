---
id: 19676
severity: "Medium"
---

# `ERC20TokenEmitter::buyToken` function mints more tokens to users than it should do

## Description

Users can buy governance tokens with the `ERC20TokenEmitter::buyToken()` function. In this protocol, governance token prices are determined by a linear [VRGDA](https://www.paradigm.xyz/2022/08/vrgda) calculation. The token price increases if the token supply is ahead of the schedule and decreases if it is behind the schedule.

There are also some other parameters I need to mention, which are [`creatorRateBps`](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/ERC20TokenEmitter.sol#L42) and [`entropyRateBps`](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/ERC20TokenEmitter.sol#L45).

  * **creatorRateBps:** The portion that goes to the creator anytime a token is bought.
  * **entropyRateBps:** The portion of the creator’s cut that is paid directly as ETH. The remaining part of the creator’s cut is used to buy governance tokens for the creator.

For example, if the creator rate is 10%, the entropy rate is 50%, and a user wants to buy 100 ETH worth of tokens:  
- Creator cut is 10 ETH  
- 5 ETH will be sent directly to the creator  
- The other 5 ETH will be used to buy governance tokens for the creator.  
- The user will get 90 ETH worth of governance tokens.

This is the main logic in the `ERC20TokenEmitter` contract.

Now, let’s examine the `buyToken` function:  

```solidity
function buyToken(
    address[] calldata addresses,
    uint[] calldata basisPointSplits,
    ProtocolRewardAddresses calldata protocolRewardsRecipients
) public payable nonReentrant whenNotPaused returns (uint256 tokensSoldWad) {
    // ... some code

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
    int totalTokensForBuyers = toPayTreasury > 0 ? getTokenQuoteForEther(toPayTreasury) : int(0); //@audit-issue tokensForCreators and tokensForBuyers are calculated separately based on their proportional ether payments. This breaks VRGDA logic because these separate calculation are both made according to the current token supply. These two calculations should not be independent of each other

    //Transfer ETH to treasury and update emitted
    emittedTokenWad += totalTokensForBuyers;
    if (totalTokensForCreators > 0) emittedTokenWad += totalTokensForCreators;

    //... rest of the code
    // funds are transferred and these amounts are minted.
}
```

This function:

  1. Calculates buyers’ ETH share in line 173.
  2. Calculates direct ETH payment to creators in line 177.
  3. Calculates token amount to mint for creators with the remaining ETH after direct payment in lines 179-180 using `getTokenQuoteForEther` function.
  4. Calculates token amount to mint for buyers in line 184 using `getTokenQuoteForEther` function
  5. After all of these calculations, it updates `emittedTokenWad` parameter.

Now let’s check the [`getTokenQuoteForEther`](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/ERC20TokenEmitter.sol#L254C2-L264C6) function:

```solidity
function getTokenQuoteForEther(uint256 etherAmount) public view returns (int gainedX) {
    //...
    return
        vrgdac.yToX({
            timeSinceStart: toDaysWadUnsafe(block.timestamp - startTime),
            sold: emittedTokenWad, //@audit it uses current state variable
            amount: int(etherAmount)
        });
}
```

As we can see in this function, how many governance tokens will be minted is calculated according to the current supply, which is `emittedTokenWad` parameter.

**Alright, what is the issue?**

The issue is that both of the `totalTokensForCreators` and `totalTokensForBuyers` parameters are **separately** calculated like they are independent of each other, and the `emittedTokenWad` is updated after that. However, this situation breaks the VRGDA logic and more tokens are minted for the same amount of ETH.

These two calculations should not be independent. Total governance tokens to mint for the total ETH payment should be calculated first, and then the governance token amounts should be proportionally distributed.

Calculating proportional ETH amounts for the buyer and the creator first, and then determining the corresponding governance tokens to mint separately, leads to a higher total number of governance tokens to be minted compared to calculating the total governance tokens required based on the overall ETH amounts to be paid.

## Proof of Concept

**Coded PoC**

Down below you can find a basic PoC that proves calculating tokens to mint separately results in many more tokens than calculating it only once with total payment.

You can use the protocol’s own setup to run this PoC  
-Copy and paste the snippet into the `ERC20TokenEmitter.t.sol` test file  
-Run it with `forge test --match-test testTokenQuoteForEther_is1plus1equal2 -vvv`

```solidity
function testTokenQuoteForEther_is1plus1equal2() public {
    int256 tokenToGetFor100ether = erc20TokenEmitter.getTokenQuoteForEther(100e18);
    int256 tokenToGetFor500ether = erc20TokenEmitter.getTokenQuoteForEther(500e18);
    int256 tokenToGetFor600ether = erc20TokenEmitter.getTokenQuoteForEther(600e18);

    // Calculating mint amounts separately will result in minting much more tokens.
    assertGt(tokenToGetFor100ether + tokenToGetFor500ether, tokenToGetFor600ether);
    console2.log("current total: ", tokenToGetFor100ether + tokenToGetFor500ether);
    console2.log("supposed total: ", tokenToGetFor600ether);
}
```

Results after running:

```
Running 1 test for test/token-emitter/ERC20TokenEmitter.t.sol:ERC20TokenEmitterTest
[PASS] testTokenQuoteForEther_is1plus1equal2() (gas: 41635)
Logs:
  current total:  586751802158813828000
  supposed total:  581798293495083372000

Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 41.60ms.

Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests).
```

## Recommendation

There are two ways to resolve this issue. An unfair but much easier one, and the fair but not that easy one

**Unfair One:**  
The protocol team should decide which side (creators or buyers) will suffer from the unfairness, and update the `emittedTokenWad` in the middle of two calculations. The latter calculation will buy tokens at a higher price.

In the example below, the change is in favour of the creators. Buyers get tokens with updated prices to keep the VRGDA logic intact.

```solidity
//Tokens to emit to creators
int totalTokensForCreators = ((msgValueRemaining - toPayTreasury) - creatorDirectPayment) > 0
    ? getTokenQuoteForEther((msgValueRemaining - toPayTreasury) - creatorDirectPayment)
    : int(0);

// Moving this here will keep the VRGDA logic intact, and the calculation for buyers will be made with updated token supply.
if (totalTokensForCreators > 0) emittedTokenWad += totalTokensForCreators;

// Tokens to emit to buyers
int totalTokensForBuyers = toPayTreasury > 0 ? getTokenQuoteForEther(toPayTreasury) : int(0);

//Transfer ETH to treasury and update emitted
emittedTokenWad += totalTokensForBuyers;
if (totalTokensForCreators > 0) emittedTokenWad += totalTokensForCreators;
```

**Fair One:**  
This one requires a little more work but it is more fair. The function should:

  1. Calculate the total ETH payment (creators + buyers) for the governance token purchase.
  2. Calculate how many total governance tokens will be minted with this total ETH payment
  3. Then mint proportional amounts to buyers and creators.

**Example** :

```solidity
// Note: This is not diff. It is just an example

// Creators ETH payment for purchase
uint256 creatorsPayment = (msgValueRemaining - toPayTreasury) - creatorDirectPayment);

// Total ETH payment for purchase (toPayTreasury is already buyers payment)
uint256 totalPayment = toPayTreasury + creatorsPayment;

// Get total governance tokens to mint
int totalGovernanceTokenAmount = getTokenQuoteForEther(totalPayment);

// Calculate proportional governance token amounts.
// Note: I didn't check this for rounding. Care should be taken if this method will be implemented
int totalTokensForCreators = (totalGovernanceTokenAmount * creatorsPayment) / totalPayment;
int totalTokensForBuyers = (totalGovernanceTokenAmount * toPayTreasury) / totalPayment;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the ERC20TokenEmitter.buyToken function where the amount of governance tokens to mint for the buyer and for the creator are calculated independently using getTokenQuoteForEther. Each call to getTokenQuoteForEther reads the current emittedTokenWad, which reflects the token supply before either portion is minted. Because the two calculations are performed sequentially but the state variable emittedTokenWad is only updated after both results are obtained, the second call uses the same supply value as the first call. This breaks the VRGDA (variable rate gradual Dutch auction) pricing model that expects a single token quote based on the total ETH being spent. As a result, the sum of the tokens minted for buyer and creator exceeds the amount that would be minted if the total ETH payment were quoted once, effectively inflating the token supply and allowing users to obtain more tokens per ETH than intended. The bug can be triggered whenever buyToken is executed with a non‑zero creatorRateBps and entropyRateBps, i.e., any purchase that splits the payment between the treasury and the creator. An attacker can repeatedly purchase tokens, causing the protocol to mint extra tokens and dilute existing holders, while the treasury receives the correct ETH amount, leading to a mismatch between the economic model and the actual token distribution. The issue was discovered during a formal audit when a test comparing getTokenQuoteForEther(100 ETH)+getTokenQuoteForEther(500 ETH) against getTokenQuoteForEther(600 ETH) showed the former to be larger, confirming over‑minting. The problem is subtle because the contract still transfers the expected ETH amounts and the token balances increase, so a casual inspection may not reveal the pricing deviation. To remediate, the function should first compute the total ETH that will be used to purchase governance tokens, call getTokenQuoteForEther once to obtain a single token amount, and then allocate that amount proportionally between buyer and creator, or alternatively update emittedTokenWad after the creator’s portion is minted before calculating the buyer’s portion. This restores the VRGDA invariant and prevents unintended token inflation. Users may notice that they receive more tokens than the price curve suggests, or that the total supply grows faster than the schedule, indicating a breach of the intended accounting logic.

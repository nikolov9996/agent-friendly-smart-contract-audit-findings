---
id: 17238
severity: "High"
---

# Draw organizer can rig the draw to favor certain participants such as their own account.

## Description

```solidity
In RandomDraw, the host initiates a draw using `startDraw()` or `redraw()` if the redraw draw expiry has passed. Actual use of Chainlink oracle is done in `_requestRoll`:
    
    request.currentChainlinkRequestId = coordinator.requestRandomWords({
        keyHash: settings.keyHash,
        subId: settings.subscriptionId,
        minimumRequestConfirmations: minimumRequestConfirmations,
        callbackGasLimit: callbackGasLimit,
        numWords: wordsRequested
    });

Use of subscription API is explained well [here](https://docs.chain.link/vrf/v2/subscription). Chainlink VRFCoordinatorV2 is called with `requestRandomWords()` and emits a random request. After `minimumRequestConfirmations` blocks, an oracle VRF node replies to the coordinator with a provable random, which supplies the random to the requesting contract via `fulfillRandomWords()` call. It is important to note the role of subscription ID. This ID maps to the subscription charged for the request, in LINK tokens. In our contract, the raffle host supplies their subscription ID as a parameter. Sufficient balance check of the request ID is not [checked](https://github.com/smartcontractkit/chainlink/blob/286a65065fcfa5e1b2362745079cdc218e40e68d/contracts/src/v0.8/VRFCoordinatorV2.sol#L370) at request-time, but rather checked in Chainlink [node](https://github.com/smartcontractkit/chainlink/blob/806ee17236ba70926a1f07d1141808b634db48b6/core/services/vrf/listener_v2.go#L346) code as well as on-chain by [VRFCoordinator](https://github.com/smartcontractkit/chainlink/blob/286a65065fcfa5e1b2362745079cdc218e40e68d/contracts/src/v0.8/VRFCoordinatorV2.sol#L594) when the request is satisfied. In the scenario where the subscriptionID lacks funds, there will be a period of 24 hours when user can top up the account and random response will be [sent](https://docs.chain.link/vrf/v2/subscription):

“Each subscription must maintain a minimum balance to fund requests from consuming contracts. If your balance is below that minimum, your requests remain pending for up to 24 hours before they expire. After you add sufficient LINK to a subscription, pending requests automatically process as long as they have not expired.”

The reason this is extremely interesting is because as soon as redraws are possible, the random response can no longer be treated as fair. Indeed, Draw host can wait until redraw cooldown passed (e.g. 1 hour), and only then fund the subscriptionID. At this point, Chainlink node will send a TX with the random response. If host likes the response (i.e. the draw winner), they will not interfere. If they don’t like the response, they can simply frontrun the Chainlink TX with a `redraw()` call. A redraw will create a new random request and discard the old requestId so the previous request will never be accepted.
    
    function fulfillRandomWords(
        uint256 _requestId,
        uint256[] memory _randomWords
    ) internal override {
        // Validate request ID
    	  // <---------------- swap currentChainlinkRequestId --->
        if (_requestId != request.currentChainlinkRequestId) {
            revert REQUEST_DOES_NOT_MATCH_CURRENT_ID();
        }
    	...
    }
    
    //<------ redraw swaps currentChainlinkRequestId --->
    request.currentChainlinkRequestId = coordinator.requestRandomWords({
        keyHash: settings.keyHash,
        subId: settings.subscriptionId,
        minimumRequestConfirmations: minimumRequestConfirmations,
        callbackGasLimit: callbackGasLimit,
        numWords: wordsRequested
    });

Chainlink docs [warn](https://docs.chain.link/vrf/v2/security) against this usage pattern of the VRF -“Don’t accept bids/bets/inputs after you have made a randomness request”. In this instance, a low subscription balance allows the host to invalidate the assumption that 1 hour redraw cooldown is enough to guarantee Chainlink answer has been received.
```

## Proof of Concept

```solidity
Owner offers a BAYC NFT for holders of their NFT collection X. Out of 10,000 tokenIDs, owner has 5,000 Xs. Rest belongs to retail users.

  1. Owner subscriptionID is left with 0 LINK balance in coordinator
  2. Redraw time is set to 2 hours
  3. Owner calls `startDraw()` which will initiate a Chainlink request
  4. Owner waits for 2 hours and then tops up their subscriptionID with sufficient LINK
  5. Owner scans the mempool for `fulfillRandomWords()`
  6. If the raffle winner is tokenID < 5000, it is owner’s token

     1. Let fulfill execute and pick up the reward
  7. If tokenID >= 5000

     1. Call `redraw()`
     2. fulfill will revert because of requestId mismatch
  8. Owner has 75% of claiming the NFT instead of 50%

Note that Forgeries draws are presumably intended as incentives for speculators to buy NFTs from specific collections. Without having a fair shot at receiving rewards from raffles, these NFTs user buys could be worthless. Another way to look at it is that the impact is theft of yield, as host can freely decrease the probability that a token will be chosen for rewards with this method.

Also, I did not categorize it as centralization risk as the counterparty is not Forgeries but rather some unknown third-party host which offers an NFT incentive program. It is a similar situation to the distinction made between 1st party and 3rd party projects [here](https://github.com/code-423n4/2022-10-juicebox-findings/issues/191).
```

## Recommendation

The root cause is that Chainlink response can arrive up to 24 hours from the most request is dispatched, while redraw cooldown can be 1 hour+. The best fix would be to enforce minimum cooldown of 24 hours.

This issue weaponized [133](https://github.com/code-423n4/2022-12-forgeries-findings/issues/133) and [194](https://github.com/code-423n4/2022-12-forgeries-findings/issues/194) to violate the fairness requirement of the protocol. Downgrading this to Medium because the 

  1. Difficulty of attack is high; you need to a) front-run the fulfillRandomWords call and b) own a meaningful % of the collection 
  2. Require to use an underfunded subscription This will flag the raffle is fishy, since the owner might as well never fund the subscription.
  3. 3rd party can mitigate this by funding the subscription.

There is another case where the chainlink node waits almost 24 hours before fulfilling the request, but I don’t think that is the normal behavior and is out of the attacker’s control.

Would like to respectfully state my case and why this finding is clearly HIGH impact. Manipulation of RNG is an extremely serious impact as it undermines assumption of fairness which is the main selling point of raffles, lotteries etc. As proof one can view [Chainlink’s ](https://immunefi.com/bounty/chainlink/) BBP which lists “Predictable or manipulable RNG that results in abuse of downstream services” as a critical impact, payable up to $3M.

I would like to relate to the conditions stated by the judge:

>   1. Difficulty of attack is high; you need to a) front-run the fulfillRandomWords call and b) own a meaningful % of the collection
> 

frontrunning is done in practically every block by MEV bots proving it’s practical and easy to do on mainnet, where the protocol is deployed. Owning a meaningful % of the collection is not necessary, as:

  1. Even with 1 / 10,000 NFTs, owner is still multiplying their chances which is a breach of fair random.
  2. The exploit can be repeated in every single raffle, exponentially multiplying their edge across time. This also highlights that the frontrunning does not have to be work every time (even though it’s high %) in order for the exploitation to work.
  3. The draw is chosen by ownership of **_settings.drawingToken** , which is a project-provided token which is already likely they have a large amount of. It is unrelated to the BAYC collection / high value NFT being given out.
  4. It is easy to see attacker can easily half the chances of any unwanted recipient to win the raffle - they would have to have the winning ticket in both rounds. Putting the subscriber’s boosted win chances aside, it’s a clear theft of user’s potential high value prize.

>   * Require to use an underfunded subscription This will flag the raffle is fishy, since the owner might as well never fund the subscription.
>   * 3rd party can mitigate this by funding the subscription
> 

It is unrealistic to expect users of the protocol to be savvy on-chain detectives and also anticipate this specific attack vector. Even so, the topping-up of the subscription is done directly subscriber -> ChainlinkVRFCoordinator, so it’s not visible by looking at the raffle contract. 

To summarize, the characteristics of this finding are much more aligned to those of High severity, than those of Medium severity.

The difficulty arises when only the raffle creator can perform the front running, not any interested MEV searcher. For sure, this is only 1 of the reason I think the risk of this issue is not High.

As the project seems to be fine with a raffle being created, but never actually started; I think when the attack require a chainlink subscription to be underfunded to begin with also kinda fall in to the “creator decided not to start raffle” category.

The argument of judging this apart from that is the raffle would looks like it completed but might not be fair, which I think is a very valid issue. However, I don’t see this as High risk given the relative difficulty as said and we seems to agree that it is fine if the raffle creator decided not to start the raffle. The end state would basically be the same.

The end states are in my opinion very different. In order to understand the full impact of the vulnerability we need to understand the context in which those raffles take place. The drawing tokens are shilled to give users a chance to win a high valued item. Their worth is correlated to the fair chance users think they have in winning the raffle. The “fake raffle” on display allows the attacker to keep profiting from ticket sales while not giving away high value. I think this is why @iainnash agreed this to be a high risk find. 

I’ve also listed several other justifications including theft of user’s chances of winning which is high impact. I’d be happy to provide additional proof of why frontrunning is easily high enough % if that is the source of difficulty observed.

> The drawing tokens are shilled to give users a chance to win a high valued item. Their worth is correlated to the fair chance users think they have in winning the raffle. 

That’s my original thought, but you and the sponsor tried to convince me the raffle is permissioned by design considering startDraw. 

If we think we need to guarantee the raffle token can get something fairly, we will also need to guarantee the raffle will, well, start. So I would say these are very similar since the ticket would be already sold anyway.

I think I might either keep everything as-is, or I am going to reinstate those other issues that I invalidated due to assuming the permissioned design, and upgrading this to High. Would love to hear more from the sponsor before making the final call.

Regarding your smart observation @gzeon , I think the idea is clearly to make the draw methods decentralized in the future, but owner controlled as a first step. However they were not aware of this exploit, which from day 1 allows to put on a show and drive draw token prices up.

[#359 (comment)](https://github.com/code-423n4/2022-12-forgeries-findings/discussions/359#discussioncomment-4693679)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a race condition between the Chainlink VRF request and the contract’s ability to issue a redraw. The draw contract stores the identifier of the most recent VRF request in a mutable variable. When the host calls redraw the contract overwrites this identifier with a new request before the previous request has been fulfilled. Because the subscription used to pay for the VRF request can be left under‑funded, the VRF coordinator will keep the request pending for up to 24 hours. The host can wait until the redraw cooldown (e.g., one hour) expires, then fund the subscription, observe the random number that will be returned, and if the number would select an opponent’s ticket, front‑run the coordinator’s fulfillRandomWords transaction with a call to redraw. This creates a new request identifier, causing the original fulfillment to revert due to a request‑ID mismatch, and the contract discards the unfavorable random outcome. Consequently the host can repeatedly bias the draw toward tickets they control, inflating their winning probability from the nominal share to a higher value. From a user’s perspective the raffle appears to run normally, but participants may never receive the advertised prize, see their chance of winning effectively disappear, or notice that the winner is always the host’s address. The issue was discovered during a security audit that examined the logic around request ID handling and the lack of a check that the subscription is funded before the request is emitted. It is difficult to notice because the contract relies on Chainlink VRF, which is generally trusted to provide unbiased randomness, and the timing window is subtle. The flaw belongs to the class of oracle response manipulation through under‑funded subscription and request‑ID race conditions. The impact violates the core fairness assumption of any lottery or raffle, resulting in potential theft of users’ expected rewards. The recommended mitigation is to enforce that the subscription holds sufficient LINK before any randomness request is sent and to set the redraw cooldown to at least the maximum pending period of the VRF (24 hours), or to make the request identifier immutable for the duration of the draw.

